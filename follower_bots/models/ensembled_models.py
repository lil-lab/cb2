# File: ensembled_models
# ----------------------
# Utilities for ensembling models with ray

import os

import ray
import torch
import torch.nn.functional as F
from follower_bots.constants import TORCH_DEVICE
from torch.distributions.categorical import Categorical

from follower_bots.models.follower_transformers import DecisionTransformer
from follower_bots.utils import load_arguments


def load_follower_model(args, args_dir, model_dir, load_best=True):
    model_args = load_arguments(args_dir)
    follower = DecisionTransformer(
        model_args["act_dim"],
        model_args["state_embed_dim"],
        model_args["cnn_option"],
        max_ep_len=model_args["max_ep_len"],
        use_timesteps=model_args["use_timesteps"],
        freeze_embeddings=model_args["freeze_embeddings"],
        num_layers=model_args["num_layers"],
        inference_temperature=model_args["inference_temperature"],
        sampling_strat=model_args["sampling_strat"],
        device=TORCH_DEVICE,
    ).to(TORCH_DEVICE)

    filename = "best_follower.pth" if load_best else "latest_follower.pth"
    state_dict, epoch, (best_swsd, epochs_since_best) = torch.load(
        os.path.join(model_dir, filename), map_location=TORCH_DEVICE
    )
    follower.load_state_dict(state_dict)
    return follower, epoch, (best_swsd, epochs_since_best)


@ray.remote
class FollowerModelWrapper:
    def __init__(self, args, args_dir, model_dir, model_name=None):
        if model_name is None:
            self.follower, _, _ = load_follower_model(
                args, args_dir, model_dir, load_best=True
            )
        else:
            base_path = os.path.join('follower_bots', 'experiments', 'pretraining',
                                     'deployment_models', f'follower_{models_name}.pt')
            self.follower = torch.load(base_path).to(TORCH_DEVICE)
            self.follower.device = TORCH_DEVICE

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
        with torch.no_grad():
            output = self.follower(
                states,
                actions,
                timesteps,
                text_conditioning,
                pos_idx,
                attention_mask,
                text_attention_mask,
                action_mask,
            )
        return output

    def sample_action(
        self,
        states,
        actions,
        timesteps,
        proc_instruction,
        pos_idx,
        attention_mask,
        text_mask,
        action_mask,
    ):
        with torch.no_grad():
            logits = self.follower.compute_logits_with_past(
                states,
                actions,
                timesteps,
                proc_instruction,
                pos_idx,
                attention_mask,
                text_mask,
                action_mask,
            )
            logits = logits.unsqueeze(1)

        return logits

    def eval(self):
        self.follower.eval()

    def train(self):
        self.follower.train()

    def reset_past_output(self):
        self.follower.reset_past_output()

    def has_past_output(self):
        return self.follower.has_past_output()


class FollowerEnsemble:
    def __init__(self, args, args_dirs, model_dirs, models_to_use=None):
        if models_to_use is None:
            self.followers = [
                FollowerModelWrapper.remote(args, args_dirs[i], model_dirs[i])
                for i in range(len(args_dirs))
            ]
        else:
            self.followers = [FollowerModelWrapper.remote(args, None, None, model_name=model_name) for model_name in models_to_use]

            
        self.ensembling_strat = args.ensembling_strat

    # Forward pass with ensembled models
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
        # Have all models perform a forward pass
        all_action_logits = ray.get(
            [
                follower.forward.remote(
                    states,
                    actions,
                    timesteps,
                    text_conditioning,
                    pos_idx,
                    attention_mask,
                    text_attention_mask,
                    action_mask,
                )
                for follower in self.followers
            ]
        )  # BxTx6 each
        return self.ensembled_probabilities(all_action_logits, action_mask)

    def ensembled_probabilities(self, all_action_logits, action_mask):
        if self.ensembling_strat == "majority_voting_raw":
            return self.majority_voting_raw(all_action_logits)
        elif self.ensembling_strat == "majority_voting_softmax":
            return self.majority_voting_softmax(all_action_logits, action_mask)
        elif self.ensembling_strat == "boltzmann_multiplication":
            return self.boltzmann_multiplication(all_action_logits)
        else:
            assert (False, "Input an invalid ensembling strategy")

    def majority_voting_raw(self, all_action_logits):
        """
        Input: A list of BxTxA tensors of action logits
        Output: Probability distribution obtained through majority voting without a softmax.
        """
        votes = self.collect_votes(all_action_logits)
        totals = torch.sum(votes, dim=2).unsqueeze(2)
        return votes / totals

    def majority_voting_softmax(self, all_action_logits, action_mask):
        """
        Input: A list of BxTxA tensors of action logits
        Output: Probability distribution obtained through majority voting with softmax.
        """
        votes = self.collect_votes(all_action_logits)
        votes.masked_fill_(action_mask.unsqueeze(1), -float("inf"))
        return F.softmax(votes, dim=2)

    def boltzmann_multiplication(self, all_action_logits):
        """
        Input: A list of BxTxA tensors of action logits
        Output: Probability distribution obtained by multiplying the probability for each
                action and renormalizing
        """
        # Compute probabilities for each model in the ensemble
        all_probs = [F.softmax(logits, dim=2) for logits in all_action_logits]

        # Get the product of each of these
        B, T, A = all_action_logits[-1].shape
        return_probs = torch.ones(B, T, A)
        for probs in all_probs:
            return_probs *= probs

        # Normalize the result
        totals = torch.sum(return_probs, dim=2).unsqueeze(2)
        return return_probs / totals

    def collect_votes(self, all_action_logits):
        # Initialize the return tensor
        B, T, A = all_action_logits[-1].shape
        return_probs = torch.zeros(B, T, A).to(all_action_logits[-1].device)

        # Get the argmax for each output and collect votes
        all_argmax = [torch.argmax(logits, dim=2) for logits in all_action_logits]
        for i in range(A):
            for argmax in all_argmax:
                return_probs[:, :, i] += (argmax == i).type(torch.float)

        return return_probs

    def sample_action(
        self,
        states,
        actions,
        timesteps,
        proc_instruction,
        pos_idx,
        attention_mask,
        text_mask,
        action_mask,
    ):
        # Have all models perform a forward pass (with memory)
        all_action_logits = ray.get(
            [
                follower.sample_action.remote(
                    states,
                    actions,
                    timesteps,
                    proc_instruction,
                    pos_idx,
                    attention_mask,
                    text_mask,
                    action_mask,
                )
                for follower in self.followers
            ]
        )  # Bx1x6 each

        # Get the probabilities
        probs = self.ensembled_probabilities(all_action_logits, action_mask).squeeze(1)

        m = Categorical(probs)
        action = m.sample()

        return action

    def eval(self):
        # Set the models to eval
        ray.get([follower.eval.remote() for follower in self.followers])

    def train(self):
        # Set the models to train
        ray.get([follower.train.remote() for follower in self.followers])

    def reset_past_output(self):
        ray.get([follower.reset_past_output.remote() for follower in self.followers])

    def has_past_output(self):
        return ray.get([self.followers[-1].has_past_output.remote()])[-1]
