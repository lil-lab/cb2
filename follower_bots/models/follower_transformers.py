# File: follower_transformers.py
# ------------------------------
# Contains transformer architectures for the follower model. Adapted from
# the Text Decision Transformer, https://github.com/Louiealbp/TDT


import torch
import torch.nn as nn
import torch.nn.functional as F
import transformers
from torch.distributions.categorical import Categorical
from transformers import GPT2Model, GPT2Tokenizer

from follower_bots.constants import (
    CNN_EMB_DIM,
    GPT_EMB_DIM,
    NUM_PROPERTIES,
    STATE_PAD_IDX,
    TEXT_PAD_IDX,
)
from follower_bots.data_utils.data_classes import ActionEnums
from follower_bots.models.hex_conv import HexConv


class DecisionTransformer(nn.Module):

    """
    This model uses GPT to model (text_1, ..., text_n, state_1, action_1, state_2, action_2, ...)
    """

    def __init__(
        self,
        act_dim,
        state_embed_dim,
        cnn_option,
        use_timesteps=True,
        num_layers=-1,
        inference_temperature=1.0,
        max_length=None,
        sampling_strat="argmax",
        max_ep_len=4096,
        action_tanh=False,
        use_ln=True,
        pre_trained=True,
        freeze_embeddings=False,
        num_frozen_layers=0,
        all_states=False,
        keep_mask=False,
        device=torch.device("cpu"),
        **kwargs
    ):
        super().__init__()
        self.act_dim = act_dim
        self.max_length = max_length
        self.device = device
        self.inference_temperature = inference_temperature
        self.past_output = None
        self.sampling_strat = sampling_strat

        self.hidden_size = GPT_EMB_DIM
        config = transformers.GPT2Config(n_embd=self.hidden_size, **kwargs)
        self.config = config
        self.initialize_gpt2(num_layers)

        self.config.all_states = all_states
        self.config.keep_mask = keep_mask
        self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

        self.use_timesteps = use_timesteps

        # Initialize timestep embeddings
        self.embed_timestep = nn.Embedding(
            max_ep_len + 1, config.n_embd, padding_idx=max_ep_len
        )
        nn.init.xavier_normal_(self.embed_timestep.weight)

        self.embed_state = nn.Sequential(
            *[
                StateEmbedder(NUM_PROPERTIES, state_embed_dim),
                get_follower_cnn_option(cnn_option, state_embed_dim),
            ]
        )
        self.embed_action = nn.Sequential(
            nn.Embedding(
                self.act_dim, config.n_embd, padding_idx=ActionEnums["PAD"].value
            ),
            nn.Tanh(),
        )
        nn.init.xavier_normal_(self.embed_action[0].weight)

        # The added words are for the PAD and the SEP tokens
        self.construct_text_embeddings(
            config.vocab_size + 1, config.n_embd, TEXT_PAD_IDX, freeze_embeddings
        )
        self.embed_ln = nn.LayerNorm(config.n_embd) if use_ln else nn.Identity()

        # note: we don't predict states or returns
        self.predict_action = nn.Sequential(
            *(
                [nn.Linear(config.n_embd, self.act_dim)]
                + ([nn.Tanh()] if action_tanh else [])
            )
        )
        nn.init.kaiming_normal_(self.predict_action[0].weight)
        nn.init.constant_(self.predict_action[0].bias, 0)

    def initialize_gpt2(self, num_layers):
        self.transformer = GPT2Model.from_pretrained("gpt2")
        if num_layers != -1:
            # Prune GPT2
            self.transformer.config.n_layer = num_layers
            self.transformer.h = self.transformer.h[:num_layers]
            self.config.n_layers = num_layers

    def construct_text_embeddings(self, vocab_size, n_embd, pad_idx, freeze_embeddings):
        assert vocab_size - 1 == pad_idx

        # Construct normally initialilzed text embeddings
        self.embed_text = nn.Embedding(vocab_size, n_embd, padding_idx=pad_idx)

        # Copy over GPT-2 embedding weights
        with torch.no_grad():
            self.embed_text.weight[:-1, :] = self.transformer.wte.weight

        # Freeze embeddings if needed
        if freeze_embeddings:
            self.embed_text.weight.requires_grad = not freeze_embeddings

    def forward(
        self,
        states,
        actions,
        timesteps,
        text_conditioning,
        pos_idx,
        attention_mask,
        text_attention_mask,
        action_mask,
    ):

        batch_size, seq_length = states.shape[0], states.shape[1]

        # Pushing to cuda
        states = states.to(self.device)
        actions = actions.to(self.device)
        timesteps = timesteps.to(self.device)
        text_conditioning = text_conditioning.to(self.device)
        pos_idx = pos_idx.to(self.device)
        attention_mask = attention_mask.to(self.device)
        text_attention_mask = text_attention_mask.to(self.device)
        action_mask = action_mask.to(self.device)

        # Embed each modality
        text_embeddings = self.embed_text(text_conditioning)  # B x T' X hidden
        state_embeddings = self.embed_state(states)  # B x T x hidden
        action_embeddings = self.embed_action(actions)  # B x T x hidden
        text_context_size = text_embeddings.shape[1]

        # time embeddings are treated similar to positional embeddings
        if self.use_timesteps:
            time_embeddings = self.embed_timestep(timesteps)  # B x T x hidden
            state_embeddings = state_embeddings + time_embeddings
            action_embeddings = action_embeddings + time_embeddings

        # which works nice in an autoregressive sense since states predict actions
        stacked_inputs = (
            torch.stack((state_embeddings, action_embeddings), dim=1)
            .permute(0, 2, 1, 3)
            .reshape(batch_size, 2 * seq_length, self.hidden_size)
        )

        # adds the text-conditioning to the front
        # new view is (T_1, T_2, T_3, ..., s_1, a_1, etc.)
        stacked_inputs = torch.cat([text_embeddings, stacked_inputs], dim=1)
        stacked_inputs = self.embed_ln(stacked_inputs)

        # to make the attention mask fit the stacked inputs, have to stack it as well
        stacked_attention_mask = (
            torch.stack((attention_mask, attention_mask), dim=1)
            .permute(0, 2, 1)
            .reshape(batch_size, 2 * seq_length)
        )

        stacked_attention_mask = torch.cat(
            [text_attention_mask, stacked_attention_mask], dim=1
        )  # B x (T' + 2T)

        # we feed in the input embeddings (not word indices) to the model
        transformer_outputs = self.transformer(
            inputs_embeds=stacked_inputs,
            attention_mask=stacked_attention_mask,
            position_ids=pos_idx,
        )
        x = transformer_outputs["last_hidden_state"]
        x = x[:, text_context_size:]

        # reshape x so that the second dimension corresponds to
        # predicting actions (0), or states (1)
        x = x.reshape(batch_size, seq_length, 2, self.hidden_size).permute(0, 2, 1, 3)

        # get predictions
        action_preds = self.predict_action(x[:, 0])

        # Apply the action mask on the predictions
        action_preds.masked_fill_(action_mask, -float("inf"))

        return action_preds

    def compute_probabilities(
        self,
        states,
        actions,
        timesteps,
        text_conditioning,
        pos_idx,
        attention_mask,
        text_attention_mask,
        action_mask,
    ):
        # Assume an output of BxTx6
        action_logits = self.forward(
            states,
            actions,
            timesteps,
            text_conditioning,
            pos_idx,
            attention_mask,
            text_attention_mask,
            action_mask,
        )
        action_probs = F.softmax(action_logits, dim=2)
        return action_probs

    def sample_action(
        self,
        states,
        actions,
        timesteps,
        text_conditioning,
        pos_idx,
        attention_mask,
        text_attention_mask,
        action_mask,
    ):
        # Get the logits
        final_prob = self.compute_logits_with_past(
            states,
            actions,
            timesteps,
            text_conditioning,
            pos_idx,
            attention_mask,
            text_attention_mask,
            action_mask,
        )

        if self.sampling_strat == "softmax":
            m = Categorical(F.softmax(final_prob, dim=1))
            action = m.sample()
        elif self.sampling_strat == "argmax":
            action = torch.argmax(final_prob, dim=1)
        else:
            assert (False, "Input an invalid sampling strategy")

        return action

    def compute_logits_with_past(
        self,
        states,
        actions,
        timesteps,
        text_conditioning,
        pos_idx,
        attention_mask,
        text_attention_mask,
        action_mask,
    ):
        # Pushing to cuda
        states = states.to(self.device)
        actions = actions.to(self.device)
        timesteps = timesteps.to(self.device)
        text_conditioning = text_conditioning.to(self.device)
        pos_idx = pos_idx.to(self.device)
        attention_mask = attention_mask.to(self.device)
        text_attention_mask = text_attention_mask.to(self.device)
        action_mask = action_mask.to(self.device)

        # Two cases requiring different approaches
        if self.past_output is None:
            a_probs, self.past_output = self.rollout_first_sample(
                states,
                actions,
                timesteps,
                text_conditioning,
                pos_idx,
                attention_mask,
                text_attention_mask,
            )
        else:
            a_probs, self.past_output = self.rollout_with_past(
                states,
                actions,
                timesteps,
                text_conditioning,
                pos_idx,
                attention_mask,
                text_attention_mask,
            )

        # Determine the final probabilities
        # Assume that the PAD token is the final index
        final_prob = a_probs[:, -1, :-1] / self.inference_temperature
        final_prob.masked_fill_(action_mask, -float("inf"))
        final_prob = final_prob.cpu()

        return final_prob

    def rollout_first_sample(
        self,
        states,
        actions,
        timesteps,
        text_conditioning,
        pos_idx,
        attention_mask,
        text_attention_mask,
    ):
        batch_size, seq_length = states.shape[0], states.shape[1]

        # Embed each modality
        text_embeddings = self.embed_text(text_conditioning)
        state_embeddings = self.embed_state(states)

        text_context_size = text_embeddings.shape[1]
        pos_idx = pos_idx[:, :-1]  # B x T' + 1

        # time embeddings are treated similar to positional embeddings
        if self.use_timesteps:
            time_embeddings = self.embed_timestep(timesteps)
            state_embeddings = state_embeddings + time_embeddings

        # Add text encoding to the front
        stacked_inputs = torch.cat([text_embeddings, state_embeddings], dim=1)
        stacked_inputs = self.embed_ln(stacked_inputs)
        stacked_attention_mask = torch.cat([text_attention_mask, attention_mask], dim=1)

        transformer_outputs = self.transformer(
            inputs_embeds=stacked_inputs,
            attention_mask=stacked_attention_mask,
            position_ids=pos_idx,
            use_cache=True,
        )
        x = transformer_outputs["last_hidden_state"]
        x = x[:, text_context_size:]  # B x 1 x hidden
        past_values = transformer_outputs["past_key_values"]

        action_preds = self.predict_action(x)
        return action_preds, past_values

    def rollout_with_past(
        self,
        states,
        actions,
        timesteps,
        text_conditioning,
        pos_idx,
        attention_mask,
        text_attention_mask,
    ):
        batch_size, seq_length = states.shape[0], states.shape[1]

        # Embed the state and the action
        state_embeddings = self.embed_state(states[:, -1:, :])  # Bx1xhidden
        action_embeddings = self.embed_action(actions[:, -2:-1])  # Bx1xhidden
        pos_idx = pos_idx[:, -3:-1]

        # Add time embeddings
        if self.use_timesteps:
            time_embeddings = self.embed_timestep(timesteps[:, -2:])  # Bx2xhidden
            state_embeddings = state_embeddings + time_embeddings[:, -1:, :]
            action_embeddings = action_embeddings + time_embeddings[:, -2:-1, :]

        stacked_inputs = (
            torch.stack((action_embeddings, state_embeddings), dim=1)
            .permute(0, 2, 1, 3)
            .reshape(batch_size, 2, self.hidden_size)
        )  # Bx2xhidden
        stacked_inputs = self.embed_ln(stacked_inputs)

        # Get the complete attention masks
        stacked_attention_mask = (
            torch.stack((attention_mask, attention_mask), dim=1)
            .permute(0, 2, 1)
            .reshape(batch_size, 2 * timesteps.shape[1])[:, :-1]
        )  # Exclude the unpredicted action
        stacked_attention_mask = torch.cat(
            [text_attention_mask, stacked_attention_mask], dim=1
        )

        transformer_outputs = self.transformer(
            inputs_embeds=stacked_inputs,
            attention_mask=stacked_attention_mask,
            position_ids=pos_idx,
            past_key_values=self.past_output,
            use_cache=True,
        )
        x = transformer_outputs["last_hidden_state"]
        past_values = transformer_outputs["past_key_values"]

        x = x.reshape(batch_size, 1, 2, self.hidden_size).permute(0, 2, 1, 3)
        action_preds = self.predict_action(x[:, 1])

        return action_preds, past_values

    def reset_past_output(self):
        self.past_output = None

    def has_past_output(self):
        return self.past_output is not None


def get_follower_cnn_option(cnn_option, in_channels):
    if cnn_option == 1:
        return ShallowFollowerStateCNN(in_channels=in_channels)
    elif cnn_option == 2:
        return DeeperFollowerStateCNN(in_channels=in_channels)
    elif cnn_option == 3:
        return ResNetFollowerStateCNN(in_channels=in_channels)
    else:
        assert (False, "Input invalid follower CNN architecture option")


class StateEmbedder(nn.Module):
    """
    Embeds the property indices held in the state representation tensor
    into P dimensional vectors, then sums the vectors up for each tile.
    """

    def __init__(self, num_properties, emb_dim):
        super().__init__()
        self.embed = nn.Embedding(num_properties, emb_dim, padding_idx=STATE_PAD_IDX)
        nn.init.xavier_normal_(self.embed.weight)

    def forward(self, x):
        embed_x = self.embed(x)  # BxTxPxHxWxemb_dim
        embed_x = torch.sum(embed_x, dim=2)  # BxTxHxWxemb_dim
        return embed_x.permute(0, 1, 4, 2, 3)


class ShallowFollowerStateCNN(nn.Module):
    """
    A 3 layer CNN using HexaConv as its convolution layer. It expects
    a Px15x15 output, then processes it with a kernel size of 7 and then
    with two layers of kernel size 5.
    """

    def __init__(self, in_channels=CNN_EMB_DIM, out_channels=GPT_EMB_DIM):
        super().__init__()
        self.l1 = nn.Sequential(
            *[
                HexConv(in_channels, in_channels * 2, 7),
                nn.LeakyReLU(),
                nn.InstanceNorm2d(in_channels * 2),
            ]
        )
        self.l2 = nn.Sequential(
            *[
                HexConv(in_channels * 2, in_channels * 4, 5),
                nn.LeakyReLU(),
                nn.InstanceNorm2d(in_channels * 4),
            ]
        )
        self.l3 = nn.Sequential(
            *[HexConv(in_channels * 4, out_channels, 5), nn.LeakyReLU()]
        )

    def forward(self, x):
        B, T, P, H, W = x.shape
        x = x.view(-1, P, H, W)

        x = self.l1(x)
        x = self.l2(x)
        return self.l3(x).view(B, T, -1)


class DeeperFollowerStateCNN(nn.Module):
    """
    A 4 layer CNN using HexaConv as its convolution layer. It expects
    an input of shape BxTxPx15x15 and processes it with 3 layers with kernel
    size 5 and one layer with kernel size 3.
    """

    def __init__(self, in_channels=CNN_EMB_DIM, out_channels=GPT_EMB_DIM):
        super().__init__()
        self.l1 = nn.Sequential(
            *[
                HexConv(in_channels, in_channels * 2, 5),
                nn.LeakyReLU(),
                nn.InstanceNorm2d(in_channels * 2),
            ]
        )
        self.l2 = nn.Sequential(
            *[
                HexConv(in_channels * 2, in_channels * 4, 5),
                nn.LeakyReLU(),
                nn.InstanceNorm2d(in_channels * 4),
            ]
        )
        self.l3 = nn.Sequential(
            *[
                HexConv(in_channels * 4, out_channels, 5),
                nn.LeakyReLU(),
                nn.InstanceNorm2d(out_channels),
            ]
        )
        self.l4 = nn.Sequential(
            *[HexConv(out_channels, out_channels, 3), nn.LeakyReLU()]
        )

    def forward(self, x, B=None, T=None):
        if B is None:
            B, T, P, H, W = x.shape
        else:
            P, H, W = x.shape[-3:]
        x = x.view(-1, P, H, W)

        x = self.l1(x)
        x = self.l2(x)
        x = self.l3(x)
        return self.l4(x).view(B, T, -1)


class ResNetFollowerStateCNN(nn.Module):
    """
    A 4 layer ResNet with HexaConv convolutions followed by a DeeperFollowerStateCNN.
    """

    def __init__(self, in_channels=CNN_EMB_DIM, out_channels=GPT_EMB_DIM):
        super().__init__()
        self.l1 = nn.Sequential(
            *[HexConv(in_channels, in_channels, 3, padding=1), nn.LeakyReLU()]
        )

        self.res_layers = nn.ModuleList([])
        for layer in range(3):
            curr_layer = [
                nn.InstanceNorm2d(in_channels),
                HexConv(in_channels, in_channels, 3, padding=1),
                nn.LeakyReLU(),
            ]
            if layer == 2:
                curr_layer.append(nn.InstanceNorm2d(in_channels))

            self.res_layers.append(nn.Sequential(*curr_layer))

        self.out_cnn = DeeperFollowerStateCNN(
            in_channels=in_channels, out_channels=out_channels
        )

    def forward(self, x):
        B, T, P, H, W = x.shape
        x = x.view(-1, P, H, W)

        x = self.l1(x)
        for layer in self.res_layers:
            x = x + layer(x)
        return self.out_cnn(x, B=B, T=T)
