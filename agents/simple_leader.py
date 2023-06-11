"""This file defines a leader that only uses a very simple language.

This is only useful for testing purposes. Theoretically, you could have
automated self-play with a simple_follower and simple_leader, but the data would
not be very diverse.
"""

import logging
from collections import deque

from agents.agent import Role
from py_client.game_endpoint import Action, GameState
from server.routing_utils import get_instruction_to_location

logger = logging.getLogger(__name__)


class SimpleLeader(object):
    def __init__(self):
        ...

    # OVERRIDES role
    def role(self) -> Role:
        return Role.LEADER

    # OVERRIDES choose_action
    def choose_action(self, game_state: GameState, action_mask=None) -> Action:
        """Chooses an action to take, given a game state.

        Action masking is not supported for this agent.

        This uses a very simple language to communicate with the follower. Instructions created specify actions in an instruction like:

        instruction: "forward, left, left, random, right, backwards".

        This corresponds with simple follower actions, which the follower will then take. "Random" results in a random action, from [left, forward, right, back].
        """
        (map, cards, turn_state, instructions, (_, follower), _) = game_state
        closest_card = _get_next_card(cards, follower)

        # If there is an instruction available, do nothing.
        if _has_instruction_available(instructions):
            return Action.EndTurn()

        # If there is no target card, send a random instruction.
        if closest_card is None:
            return Action.SendInstruction("random, random, random, random, random")

        # Otherwise, send an instruction to move to the closest card.
        return Action.SendInstruction(
            get_instruction_to_location(
                closest_card.prop_info.location, follower, map, cards
            )
        )

    def _get_action(self, game_state):
        (map, cards, turn_state, instructions, actors, feedback) = game_state
        # If no pending actions, parse them from the active instruction.
        if len(self.actions) == 0:
            active_instruction = _get_active_instruction(instructions)
            if active_instruction is None:
                logger.info(f"Num of instructions: {len(instructions)}")
                logger.info(
                    f"step() returned but no active instruction. Taking NoopAction."
                )
                return Action.NoopAction()
            self.actions.extend(_actions_from_instruction(active_instruction.text))
            self.actions.append(Action.InstructionDone(active_instruction.uuid))
            self.instructions_processed.add(active_instruction.uuid)

        # Check actions again, in case none were parsed from the instruction.
        if len(self.actions) == 0:
            # Choose a random action.
            logger.info(f"Ran out of commands in buffer. Choosing Noop.")
            return Action.NoopAction()

        # Return the next action.
        action = self.actions[0]
        self.actions.pop(0)
        return action


def _actions_from_instruction(instruction):
    actions = []
    instruction_action_codes = instruction.split(",")
    for action_code in instruction_action_codes:
        action_code = action_code.strip().lower()
        if len(action_code) == 0:
            continue
        if "forward".startswith(action_code):
            actions.append(Action.Forwards())
        elif "backward".startswith(action_code):
            actions.append(Action.Backwards())
        elif "left".startswith(action_code):
            actions.append(Action.Left())
        elif "right".startswith(action_code):
            actions.append(Action.Right())
        elif "random".startswith(action_code):
            actions.append(Action.RandomMovementAction())
    if len(actions) == 0:
        # Choose a random action.
        Action.RandomMovementAction()
    return actions


def _get_active_instruction(instructions):
    for instruction in instructions:
        if not instruction.completed and not instruction.cancelled:
            return instruction
    return None


def _get_actors(game_state):
    (
        _,
        _,
        _,
        _,
        actors,
        _,
    ) = game_state
    if len(actors) == 1:
        return (None, actors[0])
    else:
        return actors


def _card_collides(cards, new_card):
    card_colors = [card.card_init.color for card in cards]
    card_shapes = [card.card_init.shape for card in cards]
    card_counts = [card.card_init.count for card in cards]
    return (
        new_card.card_init.color in card_colors
        or new_card.card_init.shape in card_shapes
        or new_card.card_init.count in card_counts
    )


def _get_next_card(cards, follower):
    distance_to_follower = lambda c: c.prop_info.location.distance_to(
        follower.location()
    )
    selected_cards = []
    for card in cards:
        if card.card_init.selected:
            selected_cards.append(card)
    closest_card = None
    for card in cards:
        if not _card_collides(selected_cards, card):
            if closest_card is None or distance_to_follower(
                card
            ) < distance_to_follower(closest_card):
                closest_card = card
    return closest_card


def _find_path_to_card(card, follower, map, cards):
    start_location = follower.location()
    end_location = card.prop_info.location
    location_queue = deque()
    location_queue.append((start_location, [start_location]))
    card_locations = set([card.prop_info.location for card in cards])
    if start_location in card_locations:
        card_locations.remove(start_location)
    if end_location in card_locations:
        card_locations.remove(end_location)
    visited_locations = set()
    while len(location_queue) > 0:
        current_location, current_path = location_queue.popleft()
        if current_location in visited_locations:
            continue
        if current_location in card_locations:
            continue
        visited_locations.add(current_location)
        if current_location == end_location:
            return current_path
        tile = map.tile_at(current_location)
        for neighbor in tile.cell.coord.neighbors():
            if tile.cell.boundary.get_edge_between(tile.cell.coord, neighbor):
                continue
            neighbor_tile = map.tile_at(neighbor)
            if neighbor_tile.cell.boundary.get_edge_between(neighbor, tile.cell.coord):
                continue
            location_queue.append((neighbor, current_path + [neighbor]))
    return None


def _has_instruction_available(instructions):
    for instruction in instructions:
        if not instruction.completed and not instruction.cancelled:
            return True
    return False
