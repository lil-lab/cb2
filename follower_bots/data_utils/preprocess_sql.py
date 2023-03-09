# File: preprocess_sql.py
# -------------------------------
# Extracts the relevant data within the SQL dataset and stores
# it in a symbolic format for future use.

import argparse
import os
import pickle
import random
import json
import peewee
import torch

import follower_bots.data_utils.data_classes as data_cls
import server.config.config as config
import server.db_tools.db_utils as db_utils
import server.messages.map_update as map_update_msg
import server.schemas.defaults
import server.schemas.game
from follower_bots.constants import EDGE_WIDTH, ACT_DIM
from follower_bots.utils import mkdir

from server.messages.prop import PropUpdate, PropType
from server.messages.action import Action
from server.actor import Actor
from server.card import Card
from server.hex import HecsCoord
from server.schemas.util import InitialState
from server.messages.objective import ObjectiveMessage
from server.schemas import base
from server.schemas.event import Event, EventType


def get_args():
    parser = argparse.ArgumentParser(
        description="Processes past experiments in a SQL database for future training"
    )

    parser.add_argument("--output_dir", type=str, default="./follower_bots/pretraining_data")
    parser.add_argument(
        "--config_filepath", type=str, default="./follower_bots/data_configs/pretraining_examples.json"
    )

    args = parser.parse_args()
    return args


def get_tr_val_games(cfg):
    # Get valid games from config, shuffle them
    # and do a 90/10 train/val split
    games = db_utils.ListAnalysisGames(cfg)
    random.seed(42)
    random.shuffle(games)

    split = (len(games) // 10) * 9
    train_games = games[:split]
    val_games = games[split:]

    print(
        f"Following added filtering, there are {len(train_games)} train games"
        + f" and {len(val_games)} val games"
    )

    return train_games, val_games


def preprocess_games(args, games, output_dir, split_name):
    trajectories = []

    # Go through each game provided
    num_instructions = 0
    ParentEvent = Event.alias()
    for game in games:
        # Get all events associated with the current game
        game_events = (
            Event.select()
            .join(
                ParentEvent,
                peewee.JOIN.LEFT_OUTER,
                on=(Event.parent_event == ParentEvent.id),
            )
            .where(Event.game_id == game.id)
            .order_by(Event.server_time)
        )

        # Iterate over each active instruction
        instructions = game_events.where(Event.type == EventType.INSTRUCTION_SENT)
        instructions = instructions.order_by(Event.server_time)
        for inst_count, instruction in enumerate(instructions):
            # First extract the instruction text
            instruction_activation = get_instruction_activation(instruction)
            if instruction_activation is None:
                continue
            text = ObjectiveMessage.from_json(instruction.data).text

            # Next extract the actions the follower took
            actions, moves = get_actions(instruction)

            # Determine whether to skip the instruction
            if skip_instruction(instruction, actions, split_name):
                continue

            static_map, map = get_static_map_info(game_events)
            dynamic_maps = get_dynamic_map_info(game_events, instruction, actions, moves)
            final_follower_pos, change_grid, special_cards = get_swsd_information(
                dynamic_maps, instruction, moves
            )
            action_masks = get_action_masks(map, game_events, instruction, moves, actions)

            trajectories.append(
                (
                    text,
                    static_map,
                    dynamic_maps,
                    actions,
                    game.id,
                    instruction_activation.id,
                    final_follower_pos,
                    change_grid,
                    special_cards,
                    action_masks,
                    inst_count
                )
            )

            num_instructions += 1
            if num_instructions % 150 == 0:
                print(f"Instruction {num_instructions} in {split_name}")

    datapath = os.path.join(output_dir, f"pretrain_{split_name}.pkl")
    with open(datapath, "wb") as f:
        pickle.dump(trajectories, f)

    print(f"Finished {split_name} processing!")


def get_instruction_activation(instruction):
    activation_query = instruction.children.where(
        Event.type == EventType.INSTRUCTION_ACTIVATED
    )
    if not activation_query.exists():
        return None
    else:
        return activation_query.get()


def instruction_is_completed(instruction):
    completion_query = instruction.children.where(
        Event.type == EventType.INSTRUCTION_DONE
    )
    return completion_query.exists()


def instruction_is_cancelled(instruction):
    cancellation_query = instruction.children.where(
        Event.type == EventType.INSTRUCTION_CANCELLED
    )
    return cancellation_query.exists()


def get_actions(instruction):
    # First extract the follower moves from the SQL
    moves = instruction.children.where(
        Event.type == EventType.ACTION, Event.role == "Role.FOLLOWER"
    )
    moves = moves.order_by(Event.server_time)

    # Get the action enums
    actions = [data_cls.ActionEnums[move.short_code] for move in moves]
    if instruction_is_completed(instruction):
        actions.append(data_cls.ActionEnums["DONE"])

    return actions, moves


def skip_instruction(instruction, actions, split):
    # If the instruction has no actions associated with it, skip
    if len(actions) == 0:
        return True
    elif split == "val":
        # For validation, only use completed instructions
        return not instruction_is_completed(instruction)
    else:
        # For training, skip cancelled instructions
        return instruction_is_cancelled(instruction)


def get_static_map_info(game_events):
    # Extract information about the static props on the game map
    map_events = game_events.select().where(Event.type == EventType.MAP_UPDATE)
    map_events = map_events.order_by(Event.server_time).get().data
    map_update = map_update_msg.MapUpdate.from_json(map_events)
    return data_cls.StaticMap(map_update), map_update


def get_dynamic_map_info(game_events, instruction, actions, moves):
    dynamic_maps = []
    for i, action in enumerate(actions):
        if i < len(moves):
            dynamic_map = get_regular_dynamic_map(game_events, instruction, moves[i])
        else:
            dynamic_map = get_done_dynamic_map(game_events, instruction)

        dynamic_maps.append(dynamic_map)

    return dynamic_maps

def get_regular_dynamic_map(game_events, instruction, move):
    # Extract follower information from the move
    follower_location = move.location
    follower_orientation = (move.orientation - 60) % 360

    # Extract leader position before this move
    leader_location, leader_orientation = get_leader_coords(
        game_events, instruction, move
    )

    # Get the cards on the map immediately before the follower moves
    cards = get_cards_before(game_events, instruction, move)

    dynamic_map = data_cls.DynamicMap(
        cards,
        follower_location,
        follower_orientation,
        leader_location,
        leader_orientation,
    )

    return dynamic_map

def get_done_dynamic_map(game_events, instruction):
    # First get the instruction done event
    instruction_done = game_events.select().where(Event.type == EventType.INSTRUCTION_DONE,
                                                  Event.short_code == instruction.short_code)
    instruction_done = instruction_done.order_by(Event.server_time).get()

    # Determine the positions
    follower_location, follower_orientation = get_agent_coords(game_events, instruction_done, 'FOLLOWER')
    leader_location, leader_orientation = get_agent_coords(game_events, instruction_done, 'LEADER')

    # Get the cards on the map immediately before the follower moves
    cards = get_cards_before(game_events, instruction, instruction_done, done=True)

    dynamic_map = data_cls.DynamicMap(
        cards,
        follower_location,
        follower_orientation,
        leader_location,
        leader_orientation,
    )

    return dynamic_map

def get_leader_coords(game_events, instruction, move):
    # Get all leader moves before the current move
    leader_moves = game_events.select().where(
        Event.type == EventType.ACTION,
        Event.role == "Role.LEADER",
        Event.server_time < move.server_time,
    )
    leader_moves = leader_moves.order_by(Event.server_time)

    if len(leader_moves) == 0:
        # Leader did not take an action before, return spawn positions
        initial_state = (
            game_events.select().where(Event.type == EventType.INITIAL_STATE).get()
        )        
        initial_state = InitialState.from_json(initial_state.data)
        leader_location = initial_state.leader_position
        leader_orientation = (initial_state.leader_rotation_degrees - 60) % 360
    else:
        leader_move = leader_moves[-1]

        # Reconstruct position and rotation following last action
        leader_action = Action.from_json(leader_move.data)
        pos_before = leader_move.location        
        pos_delta = leader_action.displacement
        leader_location = HecsCoord.add(pos_before, pos_delta)

        orientation_before = leader_move.orientation
        orientation_delta = leader_action.rotation
        leader_orientation = (orientation_before + orientation_delta - 60) % 360

    return leader_location, leader_orientation

def get_agent_coords(game_events, instruction_done, agent_type):
    # Only called for done actions

    # Get all moves before the current move
    moves = game_events.select().where(
        Event.type == EventType.ACTION,
        Event.role == f"Role.{agent_type}",
        Event.server_time <= instruction_done.server_time,
    )
    moves = moves.order_by(Event.server_time)

    if len(moves) == 0:
        # Agent did not take an action before, return spawn positions
        initial_state = (
            game_events.select().where(Event.type == EventType.INITIAL_STATE).get()
        )        
        initial_state = InitialState.from_json(initial_state.data)
        if agent_type == "FOLLOWER":
            location = initial_state.follower_position
            orientation = (initial_state.follower_rotation_degrees - 60) % 360
        else:
            location = initial_state.leader_position
            orientation = (initial_state.leader_rotation_degrees - 60) % 360
    else:
        move = moves[-1]

        # Reconstruct position and rotation following last action
        last_action = Action.from_json(move.data)
        pos_before = move.location        
        pos_delta = last_action.displacement
        location = HecsCoord.add(pos_before, pos_delta)

        orientation_before = move.orientation
        orientation_delta = last_action.rotation
        orientation = (orientation_before + orientation_delta - 60) % 360

    return location, orientation

def get_cards_before(game_events, instruction, move, done=False):
    # Get all card events
    card_types = [EventType.CARD_SPAWN, EventType.CARD_SELECT,
                  EventType.CARD_SET, EventType.PROP_UPDATE]
    if done:
        card_events = game_events.where(Event.type << card_types,
                                        Event.server_time <= move.server_time)        
    else:
        card_events = game_events.where(Event.type << card_types,
                                        Event.server_time < move.server_time)
    card_events = card_events.order_by(Event.server_time)

    # Iterate over each card event
    props = []
    for event in card_events:
        if event.type == EventType.CARD_SET:
            data = json.loads(event.data)
            cards_ids = set([int(card_dict["id"]) for card_dict in data["cards"]])
            props = [prop for prop in props if prop.id not in cards_ids]
        elif event.type == EventType.CARD_SPAWN:
            card = Card.from_json(event.data)
            props.append(card.prop())
        elif event.type == EventType.CARD_SELECT:
            card = Card.from_json(event.data)
            for prop in props:
                if prop.id == card.id:
                    prop.card_init.selected = card.selected
                    break
        else:
            prop_update = PropUpdate.from_json(event.data)
            props = [prop for prop in prop_update.props if prop.prop_type == PropType.CARD]

    return props


def get_swsd_information(dynamic_maps, instruction, moves):
    instruction_completed = instruction_is_completed(instruction)
    final_follower_pos = get_final_follower_pos(
        dynamic_maps[-1], instruction_completed, moves
    )
    change_grid, special_cards = get_change_grid(dynamic_maps)
    return final_follower_pos, change_grid, special_cards


def get_final_follower_pos(dynamic_map, completed_instruction, moves):
    # Get the final follower position
    if completed_instruction:
        final_follower_pos = dynamic_map.get_follower_loc()
    else:
        # Must compute the end point
        last_move = [move for move in moves][-1]

        pos_before = last_move.location
        pos_delta = Action.from_json(last_move.data).displacement
        final_follower_pos = HecsCoord.add(pos_before, pos_delta)
        final_follower_pos = final_follower_pos.to_offset_coordinates()[::-1]

    return final_follower_pos


def get_change_grid(dynamic_maps):
    change_grid = torch.zeros(EDGE_WIDTH, EDGE_WIDTH)
    special_cards = set()

    # Follow the follower as they execute the instruction
    for i in range(len(dynamic_maps) - 1):
        map1, map2 = dynamic_maps[i], dynamic_maps[i + 1]
        pos1, pos2 = map1.get_follower_loc(), map2.get_follower_loc()

        # Check if the follower moves to a card
        if pos1 != pos2:
            if map2.card_at(pos2):
                x, y = pos2
                change_grid[x, y] = 1 - change_grid[x, y]
            elif map1.card_at(pos2):
                # Completed a set
                x, y = pos2
                change_grid[x, y] = 1
                special_cards.add(pos2)

    return change_grid, special_cards

def get_action_masks(map_update, game_events, instruction, moves, actions):
    all_masks = []
    for i, action in enumerate(actions):
        mask = torch.BoolTensor([False] * (ACT_DIM - 1))

        # Construct the agent
        if i < len(moves):
            follower_loc = moves[i].location
            follower_rot = moves[i].orientation
        else:
            # First get the instruction done event
            instruction_done = game_events.select().where(Event.type == EventType.INSTRUCTION_DONE,
                                                          Event.short_code == instruction.short_code)
            instruction_done = instruction_done.order_by(Event.server_time).get()
            follower_loc, follower_rot = get_agent_coords(game_events, instruction_done, "FOLLOWER")
            follower_rot = (follower_rot + 60) % 360

        follower = Actor(0, 0, 0, follower_loc)
        follower._projected_heading = follower_rot

        # Determine if you can perform a forward action
        forward = follower.ForwardLocation()
        if map_update.get_edge_between(follower_loc, forward):
            mask[data_cls.ActionEnums["MF"].value] = True

        # Determine if you can perform a backward action
        backward = follower.BackwardLocation()
        if map_update.get_edge_between(follower_loc, backward):
            mask[data_cls.ActionEnums["MB"].value] = True

        all_masks.append(mask)

    all_masks = torch.stack(all_masks, dim=0)  # Tx5
    T = all_masks.shape[0]
    padding = torch.BoolTensor([True]).unsqueeze(1).repeat(T, 1)
    all_masks = torch.cat([all_masks, padding], dim=1)  # Tx6

    return all_masks


def save_leader_games(args, games, output_dir):
    leader_trajectories = {}

    # Go through each game provided
    num_instructions = 0
    ParentEvent = Event.alias()
    for game in games:
        # Get all events associated with the current game
        game_events = (
            Event.select()
            .join(
                ParentEvent,
                peewee.JOIN.LEFT_OUTER,
                on=(Event.parent_event == ParentEvent.id),
            )
            .where(Event.game_id == game.id)
            .order_by(Event.server_time)
        )

        # Iterate over each active instruction
        instructions = game_events.where(Event.type == EventType.INSTRUCTION_SENT)
        for instruction in instructions:
            # First extract the instruction text
            instruction_activation = get_instruction_activation(instruction)
            if instruction_activation is None:
                continue

            leader_actions = get_leader_actions(game_events, instruction)
            leader_trajectories[instruction_activation.id] = leader_actions

            num_instructions += 1
            if num_instructions % 150 == 0:
                print(f"Leader processing: Instruction {num_instructions}")

    datapath = os.path.join(output_dir, f"pretrain_leader_actions.pkl")
    with open(datapath, "wb") as f:
        pickle.dump(leader_trajectories, f)


def get_leader_actions(game_events, instruction):
    # First extract the leader moves from the SQL
    all_actions = []
    moves = instruction.children.where(
        Event.type == EventType.ACTION, Event.role == "Role.LEADER"
    )
    moves = moves.order_by(Event.server_time)

    # Next, convert these into a format usable by the game wrapper
    if len(moves) > 0:
        last_turn = get_move_turn(moves[0])
        for move in moves:
            # If the turn has changed
            move_turn = get_move_turn(move)
            if last_turn != move_turn:
                all_actions.append(data_cls.ActionEnums["END_TURN"])
                last_turn = move.turn_number

            # Add the move action id
            all_actions.append(data_cls.ActionEnums[move.action_code])
    all_actions.append(data_cls.ActionEnums["END_TURN"])

    return all_actions


def get_move_turn(game_events, move):
    # Get the turn start events before the move
    turn_starts = game_events.select().where(
        Event.type == EventType.START_OF_TURN, Event.server_time < move.server_time
    )
    turn_starts = turn_starts.order_by(Event.server_time)

    if len(turn_starts) == 0:
        return 0
    else:
        return turn_starts[-1].turn_number + 1


def main():
    args = get_args()
    mkdir(args.output_dir)

    # Read the database config
    cfg = config.ReadConfigOrDie(args.config_filepath)
    print(f"Reading database from {cfg.database_path()}")
    base.SetDatabase(cfg)
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(server.schemas.defaults.ListDefaultTables())

    # Get train and val games
    train_games, val_games = get_tr_val_games(cfg)
    preprocess_games(args, train_games, args.output_dir, "train")
    preprocess_games(args, val_games, args.output_dir, "val")
    save_leader_games(args, train_games + val_games, args.output_dir)


if __name__ == "__main__":
    main()
