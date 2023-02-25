# File: train_utils
# -----------------
# Utility functions for training, such as optimizer and scheduler initialization. Also includes functions
# for evaluating the follower model using rollouts on local games.

import os
from time import time

import numpy as np
import time_machine
import torch
from transformers import AdamW, get_linear_schedule_with_warmup

from follower_bots.constants import (
    EDGE_WIDTH,
    INFERENCE_HORIZON,
    TORCH_DEVICE,
    VISIBLE_DISTANCE,
)
from follower_bots.data_utils.pyclient_utils import (
    follower_idx_to_game_action,
    generate_action_mask_mp,
    get_active_instruction_mp,
    get_local_game,
    get_pos_idx_mp,
    get_processed_actions,
    get_processed_states_mp,
    get_timesteps,
    unpack_steps,
)
from follower_bots.models.hex_conv import HexCrop
from follower_bots.models.hex_util import AxialTranslatorRotator, OffsetToAxialConverter


def get_optimizer_and_scheduler(args, tr_loader, model):
    """
    Function for initializing optimizers and schedulers for training. If the flag is set,
    will load state dicts from a checkpoint.
    """
    optimizer, scheduler = initialize_optimizer_and_scheduler(args, tr_loader, model)
    load_optimizer_and_scheduler(args, optimizer, scheduler, args.checkpoint_dir)
    return optimizer, scheduler


def initialize_optimizer_and_scheduler(args, tr_loader, model):
    # Adapted from: https://github.com/huggingface/transformers/blob/v2.5.1/examples/run_language_modeling.py

    # Get total number of steps
    t_total = len(tr_loader) * args.n_epochs

    # Prepare optimizer and schedule
    no_decay = ["bias", "LayerNorm.weight"]
    optimizer_grouped_parameters = [
        {
            "params": [
                p
                for n, p in model.named_parameters()
                if not any(nd in n for nd in no_decay)
            ],
            "weight_decay": args.wd,
        },
        {
            "params": [
                p
                for n, p in model.named_parameters()
                if any(nd in n for nd in no_decay)
            ],
            "weight_decay": 0.0,
        },
    ]
    optimizer = AdamW(optimizer_grouped_parameters, lr=args.lr, eps=args.adam_epsilon)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=args.warmup_steps, num_training_steps=t_total
    )
    return optimizer, scheduler


def load_optimizer_and_scheduler(
    args, optimizer, scheduler, checkpoint_dir
):
    if args.launch_from_checkpoint and os.path.exists(
        os.path.join(checkpoint_dir, f"latest_follower.pth")
    ):
        optimizer.load_state_dict(
            torch.load(os.path.join(checkpoint_dir, "latest_optimizer.pt"))
        )
        scheduler.load_state_dict(
            torch.load(os.path.join(checkpoint_dir, "latest_scheduler.pt"))
        )


# Evaluation utilities


def evaluate_on_cb2(follower, val_loader, coordinator, i_uuid_to_actions):
    """Code to evaluate a follower on existing CB2 games"""
    follower.eval()
    start_time = time()

    # Perform rollouts for each instruction
    data_final_pos = []
    data_change_grid = []
    model_final_positions = []
    model_change_grids = []

    times = []
    total_timesteps = 0
    for text, text_pos_idx, text_mask, ids, swsd_info in val_loader:
        # Record human data
        all_special_cards = []
        for i, (final_pos, change_grid, special_cards) in enumerate(swsd_info):
            data_final_pos.append(torch.Tensor(final_pos))
            data_change_grid.append(change_grid)
            all_special_cards.append(special_cards)

        i_uuids = [i_uuid for _, i_uuid in ids]
        model_final_pos, model_change_grid, b_t, e_t = execute_instruction(
            coordinator,
            follower,
            text,
            text_pos_idx,
            text_mask,
            all_special_cards,
            i_uuids,
            i_uuid_to_actions,
        )
        coordinator.ForceCleanAll()

        model_final_positions.extend(model_final_pos)
        model_change_grids.extend(model_change_grid)

        times.append((b_t, e_t))
        total_timesteps += len(ids)
        print(f"Processed {total_timesteps} instructions")

    print(f"It took {time() - start_time} seconds to evaluate everything")
    print(
        f"An individual batch took {np.mean([t[0] for t in times])} seconds on average"
    )
    print(
        f"Inference per batch took {np.mean([t[1] for t in times])} seconds on average"
    )

    return compute_results(
        data_final_pos, data_change_grid, model_final_positions, model_change_grids
    )


def compute_results(
    data_final_pos, data_change_grid, model_final_positions, model_change_grids
):
    # Compute scores for average card accuracy
    change_grid_matches = check_if_grids_match(data_change_grid, model_change_grids)
    average_accuracy = torch.mean(change_grid_matches).item()
    matching_cases = change_grid_matches == 1
    mismatched_cases = change_grid_matches == 0

    # Compute average distance
    hex_distances = compute_final_pos_distances(data_final_pos, model_final_positions)
    average_distance = torch.mean(hex_distances).item()
    correct_avg_distance = torch.mean(hex_distances[matching_cases]).item()
    false_avg_distance = torch.mean(hex_distances[mismatched_cases]).item()

    # Compute SWSD
    swsd = torch.mean(change_grid_matches / (1.0 + hex_distances)).item()

    # Compute precision and recall
    average_recall, average_precision = compute_recall_and_precision(
        data_change_grid, model_change_grids
    )

    return (
        average_accuracy,
        swsd,
        (average_distance, correct_avg_distance, false_avg_distance),
        (average_recall, average_precision),
    )


def compute_recall_and_precision(data_grid, model_grid):
    # Get the mismatched subset
    data_grid = reshape_change_grid(data_grid)
    model_grid = reshape_change_grid(model_grid)

    # Get number of changes for each
    data_changes = torch.sum(data_grid, dim=1).type(torch.float)
    model_changes = torch.sum(model_grid, dim=1).type(torch.float)

    # Get recall
    matches = torch.sum((data_grid == model_grid) * (data_grid > 0), dim=1).type(
        torch.float
    )
    nonzero_data = data_changes > 0
    recall = torch.mean(matches[nonzero_data] / data_changes[nonzero_data]).item()

    # Get precision
    nonzero_model = model_changes > 0
    precision = torch.mean(matches[nonzero_model] / model_changes[nonzero_model]).item()

    return recall, precision


def check_if_grids_match(grids1, grids2):
    # Process and reshape for quick computation
    grids1 = reshape_change_grid(grids1)
    grids2 = reshape_change_grid(grids2)
    grid_matches = torch.all(grids1 == grids2, dim=1).type(torch.float)
    return grid_matches


def reshape_change_grid(grid):
    grid = torch.stack(grid, dim=0)
    grid = grid.to(TORCH_DEVICE)
    grid = grid.view(-1, EDGE_WIDTH**2)
    return grid


def compute_final_pos_distances(pos1, pos2):
    # Convert the positions to axial coordinates from offset coords
    axial_pos1 = convert_to_axial(pos1)
    axial_pos2 = convert_to_axial(pos2)

    # Compute hex distance for each position
    term_1 = torch.abs(axial_pos1[:, 0] - axial_pos2[:, 0])  # abs(a.q - b.q)
    term_2 = torch.abs(
        axial_pos1.sum(dim=1) - axial_pos2.sum(dim=1)
    )  # abs(a.q + a.r - b.q - b.r)
    term_3 = torch.abs(axial_pos1[:, 1] - axial_pos2[:, 1])  # abs(a.r - b.r)
    return (term_1 + term_2 + term_3) / 2


def convert_to_axial(pos):
    # Assume a list of position tensors
    pos = torch.stack(pos, dim=0).to(TORCH_DEVICE)  # Bx2
    r = pos[:, 0]
    q = pos[:, 1]

    # Compute u and v
    v = q
    add_u = (EDGE_WIDTH - 1) // 2
    u = r - v // 2 + add_u

    # Combine them into a tensor
    return torch.stack([u, v], dim=1)


def execute_instruction(
    coordinator,
    follower,
    text,
    pos_idx,
    text_mask,
    all_special_cards,
    i_uuids,
    i_uuid_to_actions,
):
    # To avoid bugs related to machine speed
    time_traveller = time_machine.travel(0, tick=True)
    timer = time_traveller.start()
    start_time = time()
    execution_time = 0

    # Initialize the games
    total_timesteps = 0
    insts = len(i_uuids)
    timelapse_start = time()
    games = [
        get_local_game(coordinator, i_uuids[i].strip(), i_uuid_to_actions)
        for i in range(insts)
    ]
    change_trackers = [ChangeTracker() for _ in i_uuids]

    # Setup instruction variables
    states, actions, timesteps, attention_mask = [], [], [], None
    initial_states = [games[i].initial_state() for i in range(insts)]
    (
        maps,
        all_cards,
        turn_states,
        instructions,
        all_actors,
        feedbacks,
        update_trackers,
    ) = unpack_steps(initial_states)
    active_instructions = get_active_instruction_mp(instructions)

    for i in range(insts):
        change_trackers[i].update_loc(all_actors[i], update_trackers[i])

    # Setup other reoccurring variables
    axial_converter = OffsetToAxialConverter(EDGE_WIDTH)
    translator_rotator = AxialTranslatorRotator(EDGE_WIDTH).to(TORCH_DEVICE)
    tensor_cropper = HexCrop(2 * VISIBLE_DISTANCE + 1).to(TORCH_DEVICE)

    # Iterate until all games are either over or have their instruction completed
    while (
        not all([game.over() for game in games]) and total_timesteps < INFERENCE_HORIZON
    ):
        execution_start = time()

        # Initialize model inputs
        actions = get_processed_actions(actions, bsz=insts)  # B x T
        states = get_processed_states_mp(
            states,
            maps,
            all_cards,
            all_actors,
            axial_converter,
            translator_rotator,
            tensor_cropper,
        )
        timesteps = get_timesteps(actions.shape)  # B x T
        attention_mask = torch.ones(
            *timesteps.shape, dtype=torch.long
        )  # B x T: Masking doesn't matter here
        pos_idx = get_pos_idx_mp(pos_idx)

        # Take the step
        action_mask = generate_action_mask_mp(
            [games[i].follower_mask() for i in range(insts)]
        )
        with torch.no_grad():
            action = follower.sample_action(
                states,
                actions,
                timesteps,
                text,
                pos_idx,
                attention_mask,
                text_mask,
                action_mask,
            )
        actions[:, -1] = action
        game_actions = [
            follower_idx_to_game_action(actions[i, -1], active_instructions[i].uuid)
            for i in range(insts)
        ]

        execution_time += time() - execution_start
        time_since_start = time() - timelapse_start
        timer.shift(-time_since_start)

        total_timesteps += 1
        step_outputs = [games[i].step(game_actions[i]) for i in range(insts)]
        (
            maps,
            all_cards,
            turn_states,
            instructions,
            all_actors,
            feedbacks,
            update_trackers,
        ) = unpack_steps(step_outputs)

        # Update change grids and follower locations
        for i in range(insts):
            change_trackers[i].update_grid(
                all_cards[i], all_actors[i], all_special_cards[i], update_trackers[i]
            )
            change_trackers[i].update_loc(all_actors[i], update_trackers[i])

    # Return everything
    last_locs = [change_trackers[i].get_last_loc() for i in range(insts)]
    change_grids = [change_trackers[i].get_change_grid() for i in range(insts)]
    batch_time = time() - start_time
    follower.reset_past_output()
    time_traveller.stop()

    return last_locs, change_grids, batch_time, execution_time


class ChangeTracker:
    """
    Data wrapper for the change grid produced by an agent's trajectory and for the
    agent's last position in an instruction.
    """

    def __init__(self):
        self.last_loc = None
        self.change_grid = torch.zeros(EDGE_WIDTH, EDGE_WIDTH)

    def update_grid(self, cards, actors, special_cards, update_tracker):
        if self.last_loc is not None and update_tracker:
            new_loc = get_follower_loc(actors)
            if self.last_loc != new_loc:
                if card_at(cards, new_loc):
                    x, y = new_loc
                    self.change_grid[x, y] = 1 - self.change_grid[x, y]
                elif new_loc in special_cards:
                    x, y = new_loc
                    self.change_grid[x, y] = 1

    def update_loc(self, actors, update_tracker):
        if update_tracker:
            self.last_loc = get_follower_loc(actors)

    def get_last_loc(self):
        return torch.Tensor(self.last_loc)

    def get_change_grid(self):
        return self.change_grid


def get_follower_loc(actors):
    follower_actor = [actor for actor in actors if actor.role().name == "FOLLOWER"][0]
    return follower_actor.location().to_offset_coordinates()[::-1]


def card_at(cards, loc):
    for card in cards:
        card_coord = card.prop_info.location.to_offset_coordinates()[::-1]
        if loc == card_coord:
            return True
    return False
