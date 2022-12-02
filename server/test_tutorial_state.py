"""Unit tests for tutorial state machine code."""

# This is really hacky. Modifies the default action duration of walking and
# turning to be instantaneous, so we can test realtime code path tutorial very
# quickly.
import server.messages.action as action_patch

action_patch.Turn.__defaults__ = (0.01,)
action_patch.Walk.__defaults__ = (0.01,)

import logging
import os
import unittest
from enum import IntEnum

import time_machine

from py_client.game_endpoint import Action
from py_client.local_game_coordinator import LocalGameCoordinator
from server.config.config import Config
from server.messages.rooms import Role
from server.messages.tutorials import TutorialResponseType
from server.schemas.base import (
    ConnectDatabase,
    CreateTablesIfNotExists,
    SetDatabaseForTesting,
)
from server.schemas.defaults import ListDefaultTables
from server.schemas.game import Game
from server.tutorial_steps import FOLLOWER_TUTORIAL_STEPS, LEADER_TUTORIAL_STEPS

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = ""  # Hide pygame welcome message

logger = logging.getLogger(__name__)


class UnitTestActions(IntEnum):
    NONE = 0
    WAIT_1_S = 1
    WAIT_2_S = 2
    WAIT_3_S = 3
    WAIT_4_S = 4
    WAIT_HALF_S = 5


class TutorialTest(unittest.TestCase):
    """Runs integration tests on the state machine.

    Uses the pyclient local self-play API.
    """

    def setUp(self):
        self.time_traveller = time_machine.travel(0, tick=True)
        self.timer = self.time_traveller.start()
        self.realtime = True
        logging.basicConfig(level=logging.INFO)
        self.config = Config(
            card_covers=True,
            comment="Tutorial Unit Test Config",
            live_feedback_enabled=True,
        )
        # In-memory db for test validation.
        SetDatabaseForTesting()
        ConnectDatabase()
        CreateTablesIfNotExists(ListDefaultTables())
        self.coordinator = LocalGameCoordinator(self.config)

    def tearDown(self) -> None:
        self.time_traveller.stop()

    def StartLeaderTutorial(self):
        self.game_name = self.coordinator.CreateLeaderTutorial(realtime=self.realtime)
        # For tutorials, we need to specify the endpoint role.
        self.endpoint = self.coordinator.JoinTutorial(self.game_name, Role.LEADER)

    def StartFollowerTutorial(self):
        self.game_name = self.coordinator.CreateFollowerTutorial(realtime=self.realtime)
        # For tutorials, we need to specify the endpoint role.
        self.endpoint = self.coordinator.JoinTutorial(self.game_name, Role.FOLLOWER)

    def ExecuteTutorial(self, role, action_queue):
        self.endpoint.Initialize()
        logger.info(f"============= Player role: {self.endpoint.player_role()}")
        self.coordinator.StepGame(self.game_name)
        _, _, turn_state, instructions, _, _ = self.endpoint.initial_state()
        while not self.endpoint.over() and len(action_queue) > 0:
            # Handle unit test actions separately.
            if isinstance(action_queue[0], UnitTestActions):
                if self.realtime:
                    if action_queue[0] == UnitTestActions.WAIT_1_S:
                        self.timer.shift(1)
                    elif action_queue[0] == UnitTestActions.WAIT_2_S:
                        self.timer.shift(2)
                    elif action_queue[0] == UnitTestActions.WAIT_3_S:
                        self.timer.shift(3)
                    elif action_queue[0] == UnitTestActions.WAIT_4_S:
                        self.timer.shift(4)
                    elif action_queue[0] == UnitTestActions.WAIT_HALF_S:
                        self.timer.shift(0.5)
                action_queue.pop(0)
                _, _, turn_state, instructions, _, _ = self.endpoint.step(
                    Action.NoopAction(), wait_for_turn=False
                )
                continue
            # If this is an INSTRUCTION_DONE action, make sure to auto-populated the action I_UUID with the most recent instruction.
            if action_queue[0].action_code() == Action.ActionCode.INSTRUCTION_DONE:
                action_queue[0].action = (
                    Action.ActionCode.INSTRUCTION_DONE,
                    instructions[-1].uuid,
                )
            # If it's our turn, or the next action in the queue is an interrupt/dismiss/feedback. Otherwise just step(NONE).
            if turn_state.turn == role:
                action = action_queue.pop(0)
                wait_for_turn = True
                # In the tutorial, the follower sometimes acts without instructions.
                # These trip up the GameEndpoint class, unless we add wait_for_turn=False to step.
                if role == Role.FOLLOWER:
                    wait_for_turn = False
                _, _, turn_state, instructions, _, _ = self.endpoint.step(
                    action, wait_for_turn=wait_for_turn
                )
            elif action_queue[0].action_code() in [
                Action.ActionCode.TUTORIAL_NEXT_STEP,
                Action.ActionCode.INTERRUPT,
                Action.ActionCode.NEGATIVE_FEEDBACK,
                Action.ActionCode.POSITIVE_FEEDBACK,
                Action.ActionCode.NONE,
            ]:
                action = action_queue.pop(0)
                _, _, turn_state, instructions, _, _ = self.endpoint.step(
                    action, wait_for_turn=False
                )
            else:
                _, _, turn_state, instructions, _, _ = self.endpoint.step(
                    Action.NoopAction()
                )

    def test_lead_tutorial(self):
        self.StartLeaderTutorial()
        action_queue = [
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.SendInstruction(
                "UNIT TEST -- Turn left, grab the middle card in the trio."
            ),
            Action.TutorialNextStep(),
            Action.SendInstruction("UNIT TEST -- Grab the card at edge of map."),
            Action.Forwards(),
            Action.Forwards(),
            Action.EndTurn(),
            # To wait for the follower to act, we pass 3 seconds and do some NOOP steps.
            UnitTestActions.WAIT_3_S,
            # Wait for the follower to mark instruction done.
            UnitTestActions.WAIT_HALF_S,
            # Wait till there's any incoming messages.
            Action.NoopAction(),
            Action.TutorialNextStep(),
            # Wait for the follower to mark instruction done.
            UnitTestActions.WAIT_3_S,
            Action.NoopAction(),
            Action.TutorialNextStep(),
            Action.Interrupt(),
            Action.SendInstruction(
                "UNIT TEST -- Turn around, grab the card at edge of map."
            ),
            Action.EndTurn(),
            # Wait for the follower to mark instruction done.
            UnitTestActions.WAIT_4_S,
            # Wait for the follower to mark instruction done.
            Action.TutorialNextStep(),
            Action.NegativeFeedback(),
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            # IDK why there's two next steps here... debug this.
            Action.TutorialNextStep(),
            Action.PositiveFeedback(),
            Action.TutorialNextStep(),
            Action.Backwards(),
            Action.Right(),
            Action.Right(),
            Action.Forwards(),
            Action.Forwards(),
            Action.TutorialNextStep(),
            Action.Backwards(),
            Action.Left(),
            Action.Forwards(),
            Action.Forwards(),
            Action.Right(),
            Action.Forwards(),
            Action.Backwards(),
            Action.Forwards(),
            Action.Backwards(),
            Action.Left(),
            Action.Backwards(),
            Action.Backwards(),
            Action.Left(),
            Action.Backwards(),
            Action.Backwards(),
            Action.Right(),
            Action.Forwards(),
            Action.Right(),
            Action.Forwards(),
            Action.SendInstruction(
                "UNIT TEST -- Turn around and grab the card on snowy mountain."
            ),
            Action.EndTurn(),
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            UnitTestActions.WAIT_HALF_S,
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
        ]

        self.ExecuteTutorial(Role.LEADER, action_queue)

        self.assertTrue(len(action_queue) == 0)
        self.assertEqual(
            self.endpoint.tutorial_messages()[-1].type, TutorialResponseType.COMPLETE
        )
        # We add 1 step for the COMPLETE tutorial message sent once the tutorial is over.
        self.assertEqual(
            len(LEADER_TUTORIAL_STEPS) + 1, len(self.endpoint.tutorial_messages())
        )

        # Find the most recently played game. Order by start time.
        game = Game.select().order_by(Game.start_time.desc()).get()
        self.assertTrue(game.completed)

    def test_follower_tutorial(self):
        self.StartFollowerTutorial()
        # Action UUIDs are pre-populated with empty string here.
        # Later, in ExecuteTutorial, they are automatically filled in with the
        # latest instruction UUID.
        action_queue = [
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.Right(),
            Action.Forwards(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.Forwards(),
            Action.Forwards(),
            Action.Left(),
            Action.Forwards(),
            Action.InstructionDone(""),
            Action.TutorialNextStep(),
            Action.Left(),
            Action.Left(),
            Action.Left(),
            Action.Forwards(),
            Action.Right(),
            Action.Forwards(),
            Action.Forwards(),
            Action.Right(),
            Action.Forwards(),
            Action.Right(),
            Action.Forwards(),
            Action.InstructionDone(""),
            Action.Right(),
            Action.Right(),
            Action.Right(),
            Action.Forwards(),
            Action.Left(),
            Action.Forwards(),
            Action.Forwards(),
            Action.InstructionDone(""),
            Action.Backwards(),
            Action.Forwards(),
            Action.InstructionDone(""),
            Action.Right(),
            Action.Forwards(),
            Action.InstructionDone(""),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
            Action.TutorialNextStep(),
        ]

        self.ExecuteTutorial(Role.FOLLOWER, action_queue)

        self.assertTrue(len(action_queue) == 0)
        self.assertEqual(
            self.endpoint.tutorial_messages()[-1].type, TutorialResponseType.COMPLETE
        )
        # We add 1 step for the COMPLETE tutorial message sent once the tutorial is over.
        self.assertEqual(
            len(FOLLOWER_TUTORIAL_STEPS) + 1, len(self.endpoint.tutorial_messages())
        )

        # Find the most recently played game. Order by start time.
        game = Game.select().order_by(Game.start_time.desc()).get()
        self.assertTrue(game.completed)
