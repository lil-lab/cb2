"""This file defines a follower that only understands a very simple language.

This is only useful for testing purposes. Theoretically, you could have
automated self-play with a simple_follower and simple_leader, but the data would
not be very diverse.
"""

import logging
from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin

from agents.agent import Role
from py_client.game_endpoint import Action, GameState

logger = logging.getLogger(__name__)


@dataclass
class SimpleFollowerConfig(DataClassJSONMixin):
    """Configuration for a simple follower."""

    default_action: str = "INSTRUCTION_DONE"
    """Which action to take if an instruction is received with no parsable commands.

    Must be a valid value of Action.ActionCode enum, defined in py_client.game_endpoint file.
    """


class SimpleFollower(object):
    def __init__(self, config: SimpleFollowerConfig):
        self.instructions_processed = set()
        self.actions = []
        self.config = config

    # OVERRIDES role
    def role(self) -> Role:
        return Role.FOLLOWER

    # OVERRIDES choose_action
    def choose_action(self, game_state: GameState, action_mask=None) -> Action:
        """Chooses an action to take, given a game state.

        Action masking is not supported for this agent.

        This uses a very simple language to communicate with the leader. The leader specifies actions in an instruction like:

        instruction: "forward, left, left, random, right, backwards".

        This corresponds with simple follower actions, which the follower will then immediately take. "Random" results in a random action, from [left, forward, right, back].
        """
        (map, cards, turn_state, instructions, actors, feedback) = game_state
        # If no pending actions, parse them from the active instruction.
        if len(self.actions) == 0:
            active_instruction = _get_active_instruction(instructions)
            if active_instruction is None:
                logger.info(
                    f"No active instruction available. Invalid state. Taking NoopAction."
                )
                return Action.NoopAction()
            self.actions.extend(_actions_from_instruction(active_instruction.text))
            self.actions.append(Action.InstructionDone(active_instruction.uuid))
            self.instructions_processed.add(active_instruction.uuid)

        # Check actions again, in case none were parsed from the instruction.
        if len(self.actions) == 0:
            logger.info(
                f"Ran out of commands to follow. Choosing {self.config.default_action}."
            )
            default_action_code = Action.ActionCode.from_str(self.config.default_action)
            if default_action_code == Action.ActionCode.INSTRUCTION_DONE:
                return Action.InstructionDone(active_instruction.uuid)
            return Action(default_action_code)

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
