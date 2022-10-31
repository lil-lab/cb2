"""Unit tests for state machine code."""
import logging
import unittest

from py_client.endpoint_pair import EndpointPair
from py_client.game_endpoint import Action
from py_client.local_game_coordinator import LocalGameCoordinator
from server.config.config import Config
from server.messages.rooms import Role

logger = logging.getLogger(__name__)

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


if __name__ == "__main__":
    unittest.main()
