# File: follower_demo
# -------------------
# Script for interacting with a pretrained model on a server.
# This script is focused solely on interaction and does not
# have a data collection or training goal.

import argparse
from datetime import timedelta
from random import gauss
from time import sleep, time

import follower_bots.constants as const
import torch
from follower_bots.data_utils.data_classes import ActionEnums
from follower_bots.data_utils.pyclient_utils import (
    follower_idx_to_game_action,
    generate_action_mask,
    get_active_uuid,
    get_processed_actions,
    get_processed_instructions,
    get_processed_states,
)
from follower_bots.models.model_utils import load_follower_model_for_corpora_eval

from py_client.game_endpoint import Action, Role
from py_client.remote_client import RemoteClient


def get_args():
    parser = argparse.ArgumentParser(description="Interaction with pretrained models")

    # Networking arguments
    parser.add_argument("--host", type=str, help="The address of the server to connect")
    parser.add_argument("--render", action="store_true")

    # Model loading arguments
    parser.add_argument(
        "--experiments_folder",
        type=str,
        help="The folder in which the desired experiment is held",
    )
    parser.add_argument(
        "--experiments_name",
        type=str,
        help="The name of the experiment from which to load a model",
    )
    parser.add_argument(
        "--sampling_strat",
        type=str,
        default=const.SAMPLING_STRAT,
        choices=const.SAMPLING_STRATS,
        help="The strategy to follow for sampling follower actions",
    )

    # Ensembling arguments: Will override some of past arguments
    parser.add_argument(
        "--use_ensembling",
        action="store_true",
        help="If set, will use ensembling for the continual learning experiment model",
    )
    parser.add_argument(
        "--ensemble_model_names",
        type=str,
        nargs="*",
        help="The name of the experiments from which to load models",
    )
    parser.add_argument(
        "--ensembling_strat",
        type=str,
        choices=const.ENSEMBLING_STRATS,
        default="boltzmann_multiplication",
        help="What ensembling strategy to use for ensembling",
    )

    # Demonstration model arguments
    parser.add_argument('--use_deployment_models', action='store_true',
                        help="If set, will load the models used in deployment")
    parser.add_argument('--deployment_models_to_use', type=str, nargs="*",
                        help="Expects a list of strings of the form model_{model_number}")

    # Demo arguments
    parser.add_argument(
        "--e_uuid",
        type=str,
        default="",
        help="If specified, will load the euid associated with the specified instruction",
    )

    args = parser.parse_args()
    return args


def main():
    args = get_args()

    # Load the model
    follower = load_follower_model_for_corpora_eval(args)

    # Connect to the server
    client = RemoteClient(args.host, args.render, lobby_name="bot-sandbox")
    connected, reason = client.Connect()
    assert connected, f"Unable to connect: {reason}"
    game, _ = client.JoinGame(
        timeout=timedelta(minutes=5),
        queue_type=RemoteClient.QueueType.FOLLOWER_ONLY,
        e_uuid=args.e_uuid,
    )

    # Setup instruction variables
    raw_instruction, proc_instruction, text_mask = None, None, None
    states, actions, timesteps = [], [], []
    map, cards, turn_state, instructions, actors, feedback = game.initial_state()

    # Leader start
    if turn_state.turn != Role.FOLLOWER:
        game_action = Action.NoopAction()
        map, cards, turn_state, instructions, actors, feedback = game.step(game_action)

    total_timesteps = 0
    while not game.over():
        start_time = time()

        # Initialize the instructions
        raw_instruction, proc_instruction, text_mask = get_processed_instructions(
            instructions, raw_instruction, proc_instruction, text_mask
        )
        actions = get_processed_actions(actions)
        states = get_processed_states(states, map, cards, actors)
        timesteps = torch.LongTensor([[i for i in range(states.shape[1])]])
        attention_mask = torch.ones(*states.shape[:2], dtype=torch.long)
        pos_idx = torch.arange(
            0, proc_instruction.shape[1] + 2 * timesteps.shape[1], dtype=torch.long
        ).unsqueeze(0)

        # Take the step
        if total_timesteps < const.INFERENCE_HORIZON:
            action_mask = generate_action_mask(game.action_mask())
            with torch.no_grad():
                action = follower.sample_action(
                    states,
                    actions,
                    timesteps,
                    proc_instruction,
                    pos_idx,
                    attention_mask,
                    text_mask,
                    action_mask,
                )
        else:
            action = ActionEnums["DONE"].value
        actions[:, -1] = action
        game_action = follower_idx_to_game_action(action, raw_instruction.uuid)

        inference_time = time() - start_time
        map, cards, turn_state, instructions, actors, feedback = game.step(game_action)
        total_timesteps += 1

        # Reset states if instruction terminated or done
        if not game.over():
            done_instruction = (
                game_action.action_code() == Action.ActionCode.INSTRUCTION_DONE
            )
            terminated_instruction = raw_instruction.uuid != get_active_uuid(
                instructions
            )
            if done_instruction or terminated_instruction:
                states, actions, timesteps = [], [], []
                follower.reset_past_output()
                total_timesteps = 0

        time_beyond_standard = max(0, inference_time - 0.15)
        sleep_time = max(0.1, gauss(0.7 - time_beyond_standard, 0.08))
        sleep(sleep_time)

    print(f"Game over. Score: {turn_state.score}")


if __name__ == "__main__":
    main()
