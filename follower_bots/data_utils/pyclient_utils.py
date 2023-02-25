# File: pyclient_utils
# --------------------
# Python file containing utility functions to process outputs
# sent by the pyclient.

import math

import nest_asyncio
import torch
from torch.nn.utils.rnn import pad_sequence
from transformers import GPT2Tokenizer

import server.db_tools.db_utils as db_utils
from follower_bots.constants import (
    ACT_DIM,
    EDGE_WIDTH,
    TEXT_SEP_IDX,
    TORCH_DEVICE,
    VISIBLE_DISTANCE,
)
from follower_bots.data_utils.data_classes import (
    ActionEnums,
    DynamicMap,
    MapProperty,
    StaticMap,
)
from follower_bots.models.hex_conv import HexCrop
from follower_bots.models.hex_util import AxialTranslatorRotator, OffsetToAxialConverter
from follower_bots.models.pose import Pose
from py_client.endpoint_pair import EndpointPair
from py_client.game_endpoint import Action, Role
from py_client.local_game_coordinator import LocalGameCoordinator
from server.config.config import ReadConfigOrDie

# FOLLOWER UTILITIES #


def unpack_steps(batched_step_returns):
    """
    Unpacks the step returns of multiple games
    """
    maps, cards, turn_states = [], [], []
    instructions, actors, feedback = [], [], []
    update_trackers = []

    for step_return in batched_step_returns:
        maps.append(step_return[0])
        cards.append(step_return[1])
        turn_states.append(step_return[2])
        instructions.append(step_return[3])
        actors.append(step_return[4])
        feedback.append(step_return[5])
        update_trackers.append(step_return[6])

    return maps, cards, turn_states, instructions, actors, feedback, update_trackers


def get_active_instruction(instructions):
    for instruction in instructions:
        if not instruction.completed and not instruction.cancelled:
            return instruction
    raise Exception("No instructions to follow yet it's our turn?")


def get_active_instruction_mp(instructions):
    return [get_active_instruction(instruction) for instruction in instructions]


def get_processed_instructions(
    instructions, raw_instruction, proc_instruction, text_mask
):
    curr_instruction = get_active_instruction(instructions)

    # The instruction is new: Process it
    if raw_instruction is None or curr_instruction.uuid != raw_instruction.uuid:
        proc_instruction, text_mask = process_instruction(curr_instruction.text)
    return curr_instruction, proc_instruction, text_mask


def get_active_uuid(instructions):
    curr_instruction = get_active_instruction(instructions)
    return curr_instruction.uuid


def process_instruction(instruction):
    # Tokenize instruction
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
    proc_text = instruction.lower().strip().replace(",", "")
    token_ids = tokenizer(proc_text)["input_ids"]
    token_ids.append(TEXT_SEP_IDX)

    # Convert into a tensor
    tokens = torch.LongTensor(token_ids).unsqueeze(0)  # B x T'
    text_mask = torch.ones(*tokens.shape, dtype=torch.long)
    return tokens, text_mask


def get_processed_states(states, map, cards, actors):
    # Hex conversion modules
    axial_converter = OffsetToAxialConverter(EDGE_WIDTH)
    translator_rotator = AxialTranslatorRotator(EDGE_WIDTH).to(TORCH_DEVICE)
    tensor_cropper = HexCrop(2 * VISIBLE_DISTANCE + 1).to(TORCH_DEVICE)

    # Construct hex input for current state
    property_tensors = get_property_tensor(states, map, cards, actors)  # 1xPx25x25
    axial_tensors = axial_converter(property_tensors)

    poses = get_poses(actors)
    rotated_tensors = translator_rotator(axial_tensors, poses)

    new_positions = torch.full(
        (1, 2), EDGE_WIDTH + EDGE_WIDTH // 2, device=TORCH_DEVICE
    )
    cropped_tensors = tensor_cropper(
        rotated_tensors[0], new_positions, True
    )  # 1xPx15x15

    curr_state = cropped_tensors[0].unsqueeze(0).cpu().type(torch.LongTensor)

    # Pad the states if necessary
    if states != []:
        B, T, P, H, W = states.shape
        if P < curr_state.shape[2]:
            padding = torch.full(
                (B, T, curr_state.shape[2] - P, H, W), MapProperty["PAD"].value
            )
            states = torch.cat([states, padding], dim=2)
        return torch.cat([states, curr_state], dim=1)
    else:
        return curr_state


def get_processed_states_mp(
    states,
    maps,
    all_cards,
    all_actors,
    axial_converter,
    translator_rotator,
    tensor_cropper,
):
    # Construct hex inputs for the current states
    property_tensors = []
    for map, cards, actors in zip(maps, all_cards, all_actors):
        property_tensors.append(
            get_property_tensor(states, map, cards, actors).squeeze(0)
        )  # Px25x25
    property_tensors = pad_sequence(
        property_tensors, padding_value=MapProperty["PAD"].value, batch_first=True
    )  # BxPx25x25
    axial_tensors = axial_converter(property_tensors)

    poses = get_poses_mp(all_actors)
    rotated_tensors = translator_rotator(axial_tensors, poses)

    bsz = len(maps)
    new_positions = torch.full(
        (bsz, 2), EDGE_WIDTH + EDGE_WIDTH // 2, device=TORCH_DEVICE
    )
    cropped_tensors = tensor_cropper(
        rotated_tensors[0], new_positions, True
    )  # BxPx15x15

    curr_state = cropped_tensors[0].unsqueeze(1).cpu().type(torch.LongTensor)

    # Pad the states if necessary
    if states != []:
        B, T, P, H, W = states.shape
        if P < curr_state.shape[2]:
            padding = torch.full(
                (B, T, curr_state.shape[2] - P, H, W), MapProperty["PAD"].value
            )
            states = torch.cat([states, padding], dim=2)
        return torch.cat([states, curr_state], dim=1)
    else:
        return curr_state


def get_property_tensor(states, map, cards, actors):
    properties = [[] for i in range(EDGE_WIDTH**2)]

    # Process the properties: This is not the most efficient but reuses code
    static_map = StaticMap(map)
    f_loc, f_ang, l_loc, l_ang = get_agent_coords(actors)
    dynamic_map = DynamicMap(cards, f_loc, f_ang, l_loc, l_ang)

    # Add the properties from the processed data structures
    for x in range(EDGE_WIDTH):
        for y in range(EDGE_WIDTH):
            # Add static props
            if (x, y) in static_map.coord_to_props:
                properties[x * EDGE_WIDTH + y].extend(
                    [prop.value for prop in static_map.coord_to_props[(x, y)]]
                )
            if (x, y) in dynamic_map.coord_to_props:
                properties[x * EDGE_WIDTH + y].extend(
                    [prop.value for prop in dynamic_map.coord_to_props[(x, y)]]
                )

    # Pad it
    properties = [torch.Tensor(prop) for prop in properties]
    properties = (
        pad_sequence(properties, padding_value=MapProperty["PAD"].value)
        .view(-1, EDGE_WIDTH, EDGE_WIDTH)
        .unsqueeze(0)
    )  # 1xPx25x25

    if states != []:
        B, P, H, W = properties.shape
        max_size = states.shape[2]
        if max_size > P:
            padding = torch.full((1, max_size - P, H, W), MapProperty["PAD"].value)
            properties = torch.cat([properties, padding], dim=1)

    # Push to device
    return properties.to(TORCH_DEVICE)


def get_agent_coords(actors):
    # Get follower coords
    f_loc, f_ang = None, None
    l_loc, l_ang = None, None
    for actor in actors:
        if actor.role().name == "FOLLOWER":
            f_loc = actor.location()
            f_ang = (actor.heading_degrees() - 60) % 360
        elif actor.role().name == "LEADER":
            l_loc = actor.location()
            l_ang = (actor.heading_degrees() - 60) % 360
    return f_loc, f_ang, l_loc, l_ang


def get_poses(actors):
    positions, rotations = get_pose(actors)
    return Pose(positions, rotations)


def get_pose(actors):
    follower_actor = None
    for actor in actors:
        if actor.role().name == "FOLLOWER":
            follower_actor = actor

    # Get the position and angle
    f_loc = list(follower_actor.location().to_offset_coordinates()[::-1])
    f_ang = math.radians((follower_actor.heading_degrees() - 60) % 360)

    positions = torch.Tensor([f_loc]).to(TORCH_DEVICE)
    rotations = torch.Tensor([f_ang]).to(TORCH_DEVICE)
    return positions, rotations


def get_poses_mp(all_actors):
    positions = []
    rotations = []
    for actor in all_actors:
        pos, rot = get_pose(actor)
        positions.append(pos)
        rotations.append(rot)

    positions = torch.cat(positions, dim=0)  # Bx2
    rotations = torch.cat(rotations, dim=0)  # B
    return Pose(positions, rotations)


def get_processed_actions(actions, bsz=1):
    padding = torch.full((bsz, 1), ActionEnums["PAD"].value, dtype=torch.long)
    if len(actions) == 0:
        return padding
    else:
        actions = torch.cat([actions, padding], dim=1)
        return actions


def get_timesteps(shape):
    bsz, T = shape
    timesteps = torch.arange(start=0, end=T, dtype=torch.long)
    timesteps = timesteps.unsqueeze(0).repeat(bsz, 1)
    return timesteps


def get_pos_idx_mp(pos_idx):
    # Get the final positions and add 1
    next_pos_1 = pos_idx[:, -1:] + 1
    next_pos_2 = pos_idx[:, -1:] + 2
    return torch.cat([pos_idx, next_pos_1, next_pos_2], dim=1)


def follower_idx_to_game_action(action, uuid):
    if action == ActionEnums["MF"].value:
        return Action.Forwards()
    elif action == ActionEnums["MB"].value:
        return Action.Backwards()
    elif action == ActionEnums["TR"].value:
        return Action.Right()
    elif action == ActionEnums["TL"].value:
        return Action.Left()
    elif action == ActionEnums["DONE"].value:
        return Action.InstructionDone(uuid)
    elif action == ActionEnums["PAD"].value:
        raise Exception("Pad should not be predicted as an action output")
    else:
        raise Exception("Predicted action out of bounds")


def leader_idx_to_game_action(action):
    if action.value == ActionEnums["MF"].value:
        return Action.Forwards()
    elif action.value == ActionEnums["MB"].value:
        return Action.Backwards()
    elif action.value == ActionEnums["TR"].value:
        return Action.Right()
    elif action.value == ActionEnums["TL"].value:
        return Action.Left()
    elif action.value == ActionEnums["DONE"].value:
        raise Exception("The leader should not have a INSTRUCTION DONE action")
    elif action.value == ActionEnums["PAD"].value:
        raise Exception("The leader should not have a pad action")
    elif action.value == ActionEnums["END_TURN"].value:
        return Action.EndTurn()
    else:
        raise Exception(
            f"Got action {action} with type {type(action)} for leader. This should never happen."
        )


def generate_action_mask(game_action_mask):
    # Assume that the PAD token is the final index, always
    action_mask = torch.BoolTensor([True] * (ACT_DIM - 1))

    for i in range(game_action_mask.shape[0]):
        # If an index is True in game_action_mask, we can perform the action
        if not game_action_mask[i]:
            continue

        if i == Action.ActionCode.FORWARDS.value:
            action_mask[ActionEnums["MF"].value] = False
        elif i == Action.ActionCode.BACKWARDS.value:
            action_mask[ActionEnums["MB"].value] = False
        elif i == Action.ActionCode.TURN_LEFT.value:
            action_mask[ActionEnums["TL"].value] = False
        elif i == Action.ActionCode.TURN_RIGHT.value:
            action_mask[ActionEnums["TR"].value] = False
        elif i == Action.ActionCode.INSTRUCTION_DONE.value:
            action_mask[ActionEnums["DONE"].value] = False

    # Return a 1x5 tensor
    return action_mask.unsqueeze(0)


def generate_action_mask_mp(game_action_masks):
    action_masks = [
        generate_action_mask(game_action_mask) for game_action_mask in game_action_masks
    ]
    return torch.cat(action_masks, dim=0)


# Local self-play utilities


def initialize_coordinator(args):
    nest_asyncio.apply()
    config = ReadConfigOrDie(args.config_filepath)
    db_utils.ConnectToDatabase(config)
    return LocalGameCoordinator(config)


def get_local_game(coordinator, i_uuid, i_uuid_to_actions):
    game_name = coordinator.CreateGameFromDatabase(i_uuid)
    leader_actions = i_uuid_to_actions[i_uuid]
    endpoint_pair = EndpointPair(coordinator, game_name)
    return GameWrapper(endpoint_pair, leader_actions)


class GameWrapper:
    """
    Wrapper around the EndpointPair class to rollout episodes for local evaluation.
    """

    def __init__(self, endpoint_pair, leader_actions):
        self.endpoint_pair = endpoint_pair
        self.leader_game = endpoint_pair.leader()
        self.follower_game = endpoint_pair.follower()

        self.endpoint_pair.initialize()
        self.leader_actions = leader_actions
        self.leader_idx = 0

        # Internal variables for making input processing easier
        self.done_received = False
        self.last_map = None
        self.last_cards = None
        self.last_turn_states = None
        self.last_instructions = None
        self.last_actors = None
        self.last_feedback = None

    def follower_mask(self):
        return self.endpoint_pair.follower_mask()

    def initial_state(self):
        (
            map,
            cards,
            turn_states,
            instructions,
            actors,
            feedback,
        ) = self.endpoint_pair.initial_state()

        # Ensure that the first step is always taken by a follower
        while turn_states.turn == Role.LEADER:
            (
                map,
                cards,
                turn_states,
                instructions,
                actors,
                live_feedback,
            ) = self.perform_leader_steps()

        self.last_map = map
        self.last_cards = cards
        self.last_turn_states = turn_states
        self.last_instructions = instructions
        self.last_actors = actors
        self.last_feedback = feedback

        return map, cards, turn_states, instructions, actors, feedback, True

    def perform_leader_steps(self):
        if self.leader_idx < len(self.leader_actions):
            action = self.leader_actions[self.leader_idx]
            self.leader_idx += 1
        else:
            action = Action.EndTurn()
        return self.endpoint_pair.step(action)

    def over(self):
        return self.done_received or self.endpoint_pair.over()

    def step(self, game_action):
        # Update done state
        if game_action.action_code() == Action.ActionCode.INSTRUCTION_DONE:
            self.done_received = True

        # The game is not over yet, infer normally
        if not self.over():
            (
                map,
                cards,
                turn_states,
                instructions,
                actors,
                feedback,
            ) = self.endpoint_pair.step(game_action)

            while turn_states.turn == Role.LEADER and not self.over():
                (
                    map,
                    cards,
                    turn_states,
                    instructions,
                    actors,
                    live_feedback,
                ) = self.perform_leader_steps()

            self.verify_position_changed(actors)

            self.last_map = map
            self.last_cards = cards
            self.last_turn_states = turn_states
            self.last_instructions = instructions
            self.last_actors = actors
            self.last_feedback = feedback

            return map, cards, turn_states, instructions, actors, feedback, True
        else:
            return (
                self.last_map,
                self.last_cards,
                self.last_turn_states,
                self.last_instructions,
                self.last_actors,
                self.last_feedback,
                False,
            )

    def verify_position_changed(self, actors):
        past_actor = [
            actor for actor in self.last_actors if actor.role().name == "FOLLOWER"
        ][0]
        new_actor = [actor for actor in actors if actor.role().name == "FOLLOWER"][0]

        different_pos = (
            past_actor.location().to_offset_coordinates()
            != new_actor.location().to_offset_coordinates()
        )
        different_rot = (past_actor.heading_degrees() % 360) != (
            new_actor.heading_degrees() % 360
        )
        if not (different_pos or different_rot):
            print(
                "Uh oh, the position or the rotation did not change after taking an action"
            )
            assert False

    def close(self):
        self.follower_game._reset()
        self.leader_game._reset()
