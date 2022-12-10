"""Unit tests for state machine code."""
import logging
import os
import unittest

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = ""  # Hide pygame welcome message

from py_client.endpoint_pair import EndpointPair
from py_client.game_endpoint import Action
from py_client.local_game_coordinator import LocalGameCoordinator
from server.config.config import Config
from server.messages.rooms import Role
from server.schemas.base import (
    ConnectDatabase,
    CreateTablesIfNotExists,
    SetDatabaseForTesting,
)
from server.schemas.defaults import ListDefaultTables
from server.state import FOLLOWER_MOVES_PER_TURN, LEADER_MOVES_PER_TURN

logger = logging.getLogger(__name__)


def has_instruction_available(instructions):
    for instruction in instructions:
        if not instruction.completed and not instruction.cancelled:
            return True
    return False


def get_active_instruction(instructions):
    for instruction in instructions:
        if not instruction.completed and not instruction.cancelled:
            return instruction
    return None


# Ideas for future: Make a test that starts from pre-defined point in game. Make
# test that uses realtime animations instead of instant play (local self play
# disables waiting for action animations in state machine).
class RandomRealtimeLocalSelfPlayTest(unittest.TestCase):
    """Runs integration tests on the state machine.

    Uses the pyclient local self-play API.
    """

    def setUp(self):
        logging.basicConfig(level=logging.INFO)
        self.config = Config(
            card_covers=True,
            comment="State Machine Unit Test Config",
            live_feedback_enabled=True,
        )
        # In-memory db for test validation.
        SetDatabaseForTesting()
        ConnectDatabase()
        CreateTablesIfNotExists(ListDefaultTables())
        self.coordinator = LocalGameCoordinator(self.config)
        self.game_name = self.coordinator.CreateGame(
            log_to_db=False, realtime_actions=True
        )
        self.endpoint_pair = EndpointPair(self.coordinator, self.game_name)

    def test_short_game(self):
        """Tests the shortest possible game.

        each turn, the leader and follower end their turn as quickly as possible."""
        self.endpoint_pair.initialize()
        self.coordinator.StepGame(self.game_name)
        _, _, turn_state, instructions, _, _ = self.endpoint_pair.initial_state()
        while not self.endpoint_pair.over():
            if turn_state.turn == Role.LEADER:
                # If there's an active instruction, end turn.
                action = None
                for instruction in instructions:
                    if not instruction.cancelled and not instruction.completed:
                        action = Action.EndTurn()
                if action is None:
                    action = Action.SendInstruction("TEST")
                _, _, turn_state, instructions, _, _ = self.endpoint_pair.step(action)
            else:
                instruction_uuid = None
                for instruction in instructions:
                    if not instruction.cancelled and not instruction.completed:
                        instruction_uuid = instruction.uuid
                        break
                # The follower should never not have an instruction.
                self.assertIsNotNone(instruction_uuid)
                follower_action = Action.InstructionDone(instruction_uuid)
                _, _, turn_state, instructions, _, _ = self.endpoint_pair.step(
                    follower_action
                )
        logger.info(f"Game over. Leader score: {turn_state.score}")
        # Expected tick count...
        # Tick Count | Reason
        # 0          | Initial state
        # 1          | Leader & Follower Join (fast enough, that they get counted in the same tick)
        #            | Leader sends instruction (fast enough, it gets included in the first tick)
        # Turns left == 6
        # 2          | Leader ends turn.
        # 3          | Follower completes instruction.
        # Turns left == 5
        # 4          | Leader sends instruction.
        # 5          | Leader ends turn.
        # 6          | Follower completes instruction.
        # Turns left == 4
        # 7          | Leader sends instruction.
        # 8          | Leader ends turn.
        # 9          | Follower completes instruction.
        # Turns left == 3
        # 10         | Leader sends instruction.
        # 11         | Leader ends turn.
        # 12         | Follower completes instruction.
        # Turns left == 2
        # 13         | Leader sends instruction.
        # 14         | Leader ends turn.
        # 15         | Follower completes instruction.
        # Turns left == 1
        # 16         | Leader sends instruction.
        # 17         | Leader ends turn.
        # 18         | Follower completes instruction.
        # Turns left == 0
        # 19         | Leader sends instruction.
        # 20         | Leader ends turn.
        # 21         | Follower completes instruction.
        self.assertEqual(
            self.coordinator.TickCount(self.game_name),
            21,
            "Game should have ended after 21 ticks.",
        )

    def test_move_counter(self):
        """Tests a game where the leader and follower make moves and verify their move counter
        decrements as expected."""

        self.endpoint_pair.initialize()
        self.coordinator.StepGame(self.game_name)
        (
            map_update,
            _,
            turn_state,
            instructions,
            actors,
            _,
        ) = self.endpoint_pair.initial_state()
        last_leader_moves_remaining = turn_state.moves_remaining
        leader_moved = False
        last_follower_moves_remaining = 0
        follower_moved = False
        while not self.endpoint_pair.over():
            if turn_state.turn == Role.LEADER:
                leader, follower = actors
                if turn_state.moves_remaining > 0:
                    # If we have moves remaining, use them. Get the leader's position in the map.
                    # If the space in front of us is empty, move forwards. Otherwise, turn right.
                    leader_position = leader.location()
                    in_front_of_leader = leader.location().neighbor_at_heading(
                        leader.heading_degrees()
                    )
                    if not map_update.get_edge_between(
                        leader_position, in_front_of_leader
                    ):
                        action = Action.Forwards()
                    else:
                        action = Action.Right()
                    leader_moved = True
                elif turn_state.moves_remaining == 0:
                    if has_instruction_available(instructions):
                        action = Action.EndTurn()
                    else:
                        action = Action.SendInstruction("TEST")
            elif turn_state.turn == Role.FOLLOWER:
                if len(actors) == 2:
                    (leader, follower) = actors
                else:
                    follower = actors[0]
                if turn_state.moves_remaining > 0:
                    # If we have moves remaining, use them. Get the leader's position in the map.
                    # If the space in front of us is empty, move forwards. Otherwise, turn right.
                    follower_position = follower.location()
                    in_front_of_follower = follower.location().neighbor_at_heading(
                        follower.heading_degrees()
                    )
                    if not map_update.get_edge_between(
                        follower_position, in_front_of_follower
                    ):
                        action = Action.Forwards()
                    else:
                        action = Action.Right()
                    follower_moved = True
                elif turn_state.moves_remaining == 0:
                    active_instruction = get_active_instruction(instructions)
                    if active_instruction is not None:
                        action = Action.InstructionDone(active_instruction.uuid)
                    else:
                        action = Action.NoopAction()
            # Make a move.
            (
                map_update,
                _,
                turn_state,
                instructions,
                actors,
                _,
            ) = self.endpoint_pair.step(action)
            # Check the number of turns remaining.
            if (turn_state.turn == Role.LEADER) and leader_moved:
                self.assertEqual(
                    turn_state.moves_remaining,
                    last_leader_moves_remaining - 1,
                    "Leader should have one less move remaining.",
                )
                last_leader_moves_remaining = turn_state.moves_remaining
            elif (turn_state.turn == Role.FOLLOWER) and follower_moved:
                self.assertEqual(
                    turn_state.moves_remaining,
                    last_follower_moves_remaining - 1,
                    "Follower should have one less move remaining.",
                )
                last_follower_moves_remaining = turn_state.moves_remaining
            if not leader_moved:
                last_leader_moves_remaining = LEADER_MOVES_PER_TURN
            if not follower_moved:
                last_follower_moves_remaining = FOLLOWER_MOVES_PER_TURN
            leader_moved = False
            follower_moved = False


if __name__ == "__main__":
    unittest.main()
