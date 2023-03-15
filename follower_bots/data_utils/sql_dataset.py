# File: sql_dataset.py
# --------------------
# Dataset and collation function for the pretraining data held in
# the SQL dataset. The SQL dataset is assumed to have been preprocessed
# according to preprocess_sql.py

import math
import os

import torch
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import DataLoader, Dataset
from transformers import GPT2Tokenizer

from follower_bots.constants import (
    EDGE_WIDTH,
    MAX_TIME,
    TEXT_PAD_IDX,
    TEXT_SEP_IDX,
    TORCH_DEVICE,
    VISIBLE_DISTANCE,
)
from follower_bots.data_utils.data_classes import (
    ActionEnums,
    DynamicProperty,
    MapProperty,
)
from follower_bots.data_utils.pyclient_utils import leader_idx_to_game_action
from follower_bots.models.hex_conv import HexCrop
from follower_bots.models.hex_util import AxialTranslatorRotator, OffsetToAxialConverter
from follower_bots.models.pose import Pose
from follower_bots.utils import load_pickle


class SQLDataset(Dataset):
    """
    Dataset containing follower trajectories for behavior cloning training.
    The initialization code assumes that the SQLite database holding the games
    to train on has been preprocessed into a .pkl file holding the relevant information
    for behavior cloning.
    """

    def __init__(
        self,
        dataset_path,
        split,
        device=TORCH_DEVICE,
        preprocess_path=None,
        standard_path=None,
    ):
        """
        Arguments:
        * dataset_path (str):     Path to a folder containing a preprocessed version of the
                                  SQLite database for instruction following.
        * split (str):            train or val
        * standard_path (str):    The full path to the pickle file containing the preprocessed
                                  version of the SQLite database. If None, this path will be
                                  constructed using dataset_path.
        * preprocess_path (str):  The path to which the database contents should be saved following
                                  additional preprocessing. If None, this path will be constructed
                                  using dataset_path.
        """

        # Determine where to save the dataset following preprocessing
        if preprocess_path is None:
            preprocess_path = os.path.join(
                dataset_path, f"pretrain_{split}_preprocess.pkl"
            )

        # If we've performed preprocessing once, load from saved data
        if os.path.exists(preprocess_path):
            self.load_from_preprocessed(preprocess_path, device)
        else:
            if standard_path is None:
                standard_path = os.path.join(dataset_path, f"pretrain_{split}.pkl")
            self.load_from_standard(
                standard_path, preprocess_path, device
            )

    def load_from_standard(
        self, dataset_path, preprocess_path, device=TORCH_DEVICE
    ):
        trajectories = load_pickle(dataset_path)

        self.instructions = []
        self.pos_indices = []
        self.states = []
        self.actions = []
        self.timesteps = []
        self.ids = []
        self.swsd_info = []
        self.action_masks = []

        self.device = device

        # Process the text instructions
        self.process_text(trajectories)
        print("Processed all text items")

        # Process the states
        self.process_states(trajectories)
        print("Processed all states")

        # Process actions, timesteps and ids
        self.process_others(trajectories)

        # Load the action masks
        torch.save(
            [
                self.instructions,
                self.pos_indices,
                self.states,
                self.actions,
                self.timesteps,
                self.ids,
                self.swsd_info,
                self.action_masks,
            ],
            preprocess_path,
        )

    def load_from_preprocessed(self, preprocess_path, device=TORCH_DEVICE):
        contents = torch.load(preprocess_path)

        self.instructions = contents[0]
        self.pos_indices = contents[1]
        self.states = contents[2]
        self.actions = contents[3]
        self.timesteps = contents[4]
        self.ids = contents[5]
        self.swsd_info = contents[6]
        self.action_masks = contents[7]

        self.device = device

    def process_text(self, trajectories):
        # Initialize tokenizer
        tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
        pad_index = [TEXT_PAD_IDX]

        # Tokenize each instruction and add them to list
        tokenized = self.tokenize_instructions(trajectories, tokenizer)
        max_length = max([len(token_ids) for token_ids in tokenized])

        # Add padding to each instruction
        self.pad_instructions(tokenized, max_length, pad_index)

    def process_states(self, trajectories):
        # Hex conversion modules
        axial_converter = OffsetToAxialConverter(EDGE_WIDTH)
        translator_rotator = AxialTranslatorRotator(EDGE_WIDTH).to(TORCH_DEVICE)
        tensor_cropper = HexCrop(2 * VISIBLE_DISTANCE + 1).to(TORCH_DEVICE)

        # Process the states of each instruction individually
        max_property_size = self.get_max_property_size(trajectories)
        for _, static_map, dynamic_map, _, _, _, _, _, _, _ in trajectories:
            property_tensors = self.get_property_tensor(
                static_map, dynamic_map, max_property_size
            )
            axial_tensors = axial_converter(property_tensors)

            poses = self.get_poses(dynamic_map)
            rotated_tensors = translator_rotator(axial_tensors, poses)

            new_positions = torch.full(
                (len(dynamic_map), 2), EDGE_WIDTH + EDGE_WIDTH // 2, device=TORCH_DEVICE
            )
            cropped_tensors = tensor_cropper(rotated_tensors[0], new_positions, True)

            self.states.append(
                cropped_tensors[0].cpu().type(torch.LongTensor)
            )  # Shape: TxPx(2*VISIBLE + 1)x(2*VISIBLE + 1)

    def get_max_property_size(self, trajectories):
        max_size = 0
        for _, static_map, dynamic_map, _, _, _, _, _, _, _ in trajectories:
            static_properties = self.extract_static_props(static_map)
            all_dynamic_properties = self.extract_dynamic_props(dynamic_map)

            for dynamic_props in all_dynamic_properties:
                for i, dynamic_prop in enumerate(dynamic_props):
                    static_prop = static_properties[i]
                    curr_size = len(static_prop) + len(dynamic_prop)
                    if curr_size > max_size:
                        max_size = curr_size
        return max_size

    def get_property_tensor(self, static_map, dynamic_map, max_size):
        # Get a list of lists of size 625 (25*25) where each list contains property indices
        static_properties = self.extract_static_props(static_map)
        all_dynamic_properties = self.extract_dynamic_props(dynamic_map)

        # Get properties for each tile, repeated for each timestep
        all_tiles_merged = []
        for dynamic_props in all_dynamic_properties:
            for i, dynamic_prop in enumerate(dynamic_props):
                static_prop = static_properties[i]
                all_tiles_merged.append(torch.Tensor(static_prop + dynamic_prop))

        # Pad the property lists to be of the same size: Px(625xT)
        padded_tiles = pad_sequence(
            all_tiles_merged, padding_value=MapProperty["PAD"].value
        )

        # Extract property map for each individual timestep
        return_tiles = []
        for t in range(len(dynamic_map)):
            curr_tiles = padded_tiles[
                :, t * EDGE_WIDTH**2 : (t + 1) * EDGE_WIDTH**2
            ].view(-1, EDGE_WIDTH, EDGE_WIDTH)
            return_tiles.append(curr_tiles)

        # Output: BxPx25x25 tensor
        return_tiles = torch.stack(return_tiles, dim=0)
        B, P, H, W = return_tiles.shape
        if max_size > return_tiles.shape[1]:
            padding = torch.full((B, max_size - P, H, W), MapProperty["PAD"].value)
            return_tiles = torch.cat([return_tiles, padding], dim=1)
        return return_tiles.to(self.device)

    def extract_static_props(self, static_map):
        static_properties = [[] for i in range(EDGE_WIDTH**2)]
        for (x, y), props in static_map.coord_to_props.items():
            static_properties[x * EDGE_WIDTH + y].extend([prop.value for prop in props])
        return static_properties

    def extract_dynamic_props(self, dynamic_maps):
        all_dynamic_properties = []
        for i, dynamic_map in enumerate(dynamic_maps):
            all_dynamic_properties.append([[] for j in range(EDGE_WIDTH**2)])
            for (x, y), props in dynamic_map.coord_to_props.items():
                all_dynamic_properties[i][x * EDGE_WIDTH + y].extend(
                    [prop.value for prop in props]
                )
        return all_dynamic_properties

    def get_poses(self, dynamic_maps):
        positions = []
        rotations = []

        follower_idx = DynamicProperty["FOLLOWER"]
        idx_to_rot = {
            DynamicProperty[f"FOLLOWER_ROT_{rot}"]: math.radians(rot)
            for rot in range(0, 360, 60)
        }

        for dynamic_map in dynamic_maps:
            for coord, props in dynamic_map.coord_to_props.items():
                if follower_idx in props:
                    positions.append(torch.Tensor(list(coord)))
                    for idx, rot in idx_to_rot.items():
                        if idx in props:
                            rotations.append(rot)
                    break

        positions = torch.stack(positions, dim=0).to(TORCH_DEVICE)
        rotations = torch.Tensor(rotations).to(TORCH_DEVICE)
        return Pose(positions, rotations)

    def tokenize_instructions(self, trajectories, tokenizer):
        tokenized = []
        for text, _, _, _, _, _, _, _, _, _ in trajectories:
            proc_text = text.lower().strip().replace(",", "")
            token_ids = tokenizer(proc_text)["input_ids"]

            # Add a separator to distinguish between text and state input
            token_ids.append(TEXT_SEP_IDX)

            tokenized.append(token_ids)

        return tokenized

    def pad_instructions(self, tokenized, max_length, pad_index):
        for token_ids in tokenized:
            # Add the padded position indices
            curr_pos_indices = [i for i in range(len(token_ids))]
            curr_pos_indices = [0] * (max_length - len(token_ids)) + curr_pos_indices
            self.pos_indices.append(torch.LongTensor(curr_pos_indices))

            # Add the padded text
            token_padding = pad_index * (max_length - len(token_ids))
            self.instructions.append(torch.LongTensor(token_padding + token_ids))

    def process_others(self, trajectories):
        for (
            _,
            _,
            _,
            actions,
            g_id,
            i_uuid,
            final_pos,
            change_grid,
            special_cards,
            action_masks,
        ) in trajectories:

            proc_action = torch.LongTensor([action.value for action in actions])
            self.actions.append(proc_action)

            proc_timesteps = torch.LongTensor(list(range(len(actions))))
            self.timesteps.append(proc_timesteps)

            self.ids.append((g_id, i_uuid.hex))

            self.swsd_info.append((final_pos, change_grid, special_cards))

            self.action_masks.append(action_masks)

    def __getitem__(self, idx):
        return (
            self.instructions[idx],
            self.pos_indices[idx],
            self.states[idx],
            self.actions[idx],
            self.timesteps[idx],
            self.ids[idx],
            self.swsd_info[idx],
            self.action_masks[idx],
        )

    def __len__(self):
        return len(self.instructions)


def sql_collate_fn(batch):
    """
    Processes the contents of the SQLDataset batch, primarily to pad matrices
    and to generate attention masks
    """
    text_input = []
    pos_input = []
    state_input = []
    action_input = []
    timestep_input = []
    id_input = []
    swsd_info = []
    action_masks = []

    for text, pos, s, a, t, ids, swsd, action_mask in batch:
        text_input.append(text)
        pos_input.append(pos)
        state_input.append(s)
        action_input.append(a)
        timestep_input.append(t)
        id_input.append(ids)
        swsd_info.append(swsd)
        action_masks.append(action_mask)

    # State processing
    state_input = pad_sequence(state_input, padding_value=0).permute(
        1, 0, 2, 3, 4
    )  # BxTxPxHxW

    # Text processing
    text_input = torch.stack(text_input, dim=0)
    text_mask = torch.ones(*text_input.shape, dtype=torch.long)
    pad_idx = text_input == TEXT_PAD_IDX
    text_mask[pad_idx] = 0

    # Action and timestep processing
    action_input = pad_sequence(
        action_input, padding_value=ActionEnums["PAD"].value
    ).permute(
        1, 0
    )  # BxT
    timestep_input = pad_sequence(timestep_input, padding_value=MAX_TIME).permute(
        1, 0
    )  # BxT
    action_masks = pad_sequence(action_masks, padding_value=False).permute(
        1, 0, 2
    )  # BxTx6

    # Main attention mask
    attention_mask = torch.ones(*action_input.shape, dtype=torch.long)
    pad_idx = timestep_input == MAX_TIME
    attention_mask[pad_idx] = 0

    # Position indices
    pos_input = torch.stack(pos_input, dim=0)  # B x T'
    state_pos = torch.arange(1, action_input.shape[-1] * 2 + 1, dtype=torch.long)  # 2T
    state_pos = state_pos.unsqueeze(0).repeat(action_input.shape[0], 1)  # B x 2T
    state_pos = state_pos + pos_input[:, -1].unsqueeze(1)
    pos_input = torch.cat([pos_input, state_pos], dim=1)  # B x (T' + 2T)

    return (
        state_input,
        action_input,
        timestep_input,
        text_input,
        pos_input,
        attention_mask,
        text_mask,
        action_masks,
        id_input,
        swsd_info,
    )


def sql_collate_fn_rollouts(batch):
    """
    Processes the contents of the SQLDataset batch relevant to rollout-based
    evaluation.
    """
    text_input = []
    pos_input = []
    id_input = []
    swsd_info = []

    for text, pos, _, _, _, ids, swsd, _ in batch:
        text_input.append(text)
        pos_input.append(pos)
        id_input.append(ids)
        swsd_info.append(swsd)

    # Text processing
    text_input = torch.stack(text_input, dim=0)
    text_mask = torch.ones(*text_input.shape, dtype=torch.long)
    pad_idx = text_input == TEXT_PAD_IDX
    text_mask[pad_idx] = 0
    pos_input = torch.stack(pos_input, dim=0)

    return text_input, pos_input, text_mask, id_input, swsd_info


def get_sql_dataloader_for(args, split, use_ce=False):
    if split == "train":
        shuffle = True
        collate_fn = sql_collate_fn
    else:
        shuffle = False
        collate_fn = sql_collate_fn if use_ce else sql_collate_fn_rollouts

    dset = SQLDataset(args.pretrain_dset_path, split)
    loader = DataLoader(
        dset,
        batch_size=args.batch_size,
        shuffle=shuffle,
        num_workers=args.num_workers,
        collate_fn=collate_fn,
    )
    return loader


def get_sql_dataloader(args):
    """
    Initializes dataloaders for the training and validation set. For the validation set,
    the function initializes one dataloader for RL rollout evaluation and another for computing
    cross entropy.
    """
    tr_loader = get_sql_dataloader_for(args, "train")
    val_loader = get_sql_dataloader_for(args, "val")
    val_loader_ce = get_sql_dataloader_for(args, "val", use_ce=True)
    return tr_loader, val_loader, val_loader_ce


def get_leader_actions(args):
    """
    Loads a dictionary mapping instruction event ids to a list of leader actions for
    each instruction within train and test sets. Used for evaluation.
    """
    leader_action_path = os.path.join(
        args.pretrain_dset_path, f"pretrain_leader_actions.pkl"
    )
    leader_actions = load_pickle(leader_action_path)

    new_leader_actions = {}
    for i_uuid, actions in leader_actions.items():
        proc_actions = [leader_idx_to_game_action(action) for action in actions]
        new_leader_actions[i_uuid.hex] = proc_actions
    return new_leader_actions
