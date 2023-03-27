""" This file defines a high-level API for interacting with a CB2 game. It is
intended to be used for developers creating interactive bots that play CB2.
"""
import asyncio
import dataclasses
import logging
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterator, List, Union

import numpy as np
import pygame
from mashumaro.mixins.json import DataClassJSONMixin

import server.actor as actor
import server.messages.state_sync as state_sync
from py_client.client_messages import (
    ActionsMessage,
    EndTurnMessage,
    InstructionDoneMessage,
    InstructionMessage,
    InterruptMessage,
    LeaveMessage,
    LoadScenarioMessage,
    NegativeFeedbackMessage,
    PongMessage,
    PositiveFeedbackMessage,
    TutorialNextStepMessage,
)
from py_client.follower_data_masking import (
    CensorActors,
    CensorFollowerMap,
    CensorFollowerProps,
)
from py_client.game_socket import GameSocket
from server.actor import Actor
from server.config.config import Config
from server.main import HEARTBEAT_TIMEOUT_S
from server.map_tools.visualize import GameDisplay
from server.messages import action as action_module
from server.messages import message_from_server
from server.messages.action import Action, ActionType
from server.messages.live_feedback import LiveFeedback
from server.messages.map_update import MapUpdate
from server.messages.objective import ObjectiveMessage
from server.messages.prop import Prop, PropType
from server.messages.rooms import Role
from server.messages.turn_state import TurnState

logger = logging.getLogger(__name__)

# If render=True in the constructor for Game, this controls the resulting window size.
SCREEN_SIZE = 800

BLOCKING_ZERO_TIME = 0.000001

# I dont' think I need this anymore. This is an attempt to export the Role symbol so that users of this package can access it.
Role = Role


def pygame_handle_events():
    """Checks if a key has been pressed and then exits the program."""
    try:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)
    except pygame.error as e:
        pass


async def pygame_event_handler():
    """Background task to handle pygame events.

    This is a coroutine. Recommended to start as an asyncio task and killed with
    task.Cancel().

    """
    while True:
        pygame_handle_events()
        await asyncio.sleep(0.1)


@dataclass
class GameState(DataClassJSONMixin):
    """Represents the state of the game at a given time. Unpacks to a tuple for compatibility with the old API."""

    map_update: MapUpdate
    props: List[Prop]
    turn_state: TurnState
    instructions: List[ObjectiveMessage]
    actors: List[Actor]
    live_feedback: List[LiveFeedback]

    def __iter__(
        self,
    ) -> Iterator[
        Union[
            MapUpdate,
            List[Prop],
            TurnState,
            List[ObjectiveMessage],
            List[Actor],
            List[LiveFeedback],
        ]
    ]:
        return iter(
            (
                self.map_update,
                self.props,
                self.turn_state,
                self.instructions,
                self.actors,
                self.live_feedback,
            )
        )


class Action(object):
    """Defines the actions that agents can take in-game.

    Actions are passed as the primary argument to step() to control the agent.
    """

    class ActionCode(Enum):
        NONE = 0
        FORWARDS = 1
        BACKWARDS = 2
        TURN_LEFT = 3
        TURN_RIGHT = 4
        END_TURN = 5
        INTERRUPT = 6
        SEND_INSTRUCTION = 7
        INSTRUCTION_DONE = 8
        POSITIVE_FEEDBACK = 9
        NEGATIVE_FEEDBACK = 10
        TUTORIAL_NEXT_STEP = 11
        LOAD_SCENARIO = 12
        MAX = 12

    # Helper initialization functions.
    @staticmethod
    def Forwards():
        return Action(Action.ActionCode.FORWARDS)

    @staticmethod
    def Backwards():
        return Action(Action.ActionCode.BACKWARDS)

    @staticmethod
    def Left():
        return Action(Action.ActionCode.TURN_LEFT)

    @staticmethod
    def Right():
        return Action(Action.ActionCode.TURN_RIGHT)

    @staticmethod
    def EndTurn():
        return Action(Action.ActionCode.END_TURN)

    @staticmethod
    def Interrupt():
        return Action(Action.ActionCode.INTERRUPT)

    @staticmethod
    def SendInstruction(instruction):
        return Action(Action.ActionCode.SEND_INSTRUCTION, instruction)

    @staticmethod
    def InstructionDone(iuuid):
        return Action(Action.ActionCode.INSTRUCTION_DONE, i_uuid=iuuid)

    @staticmethod
    def PositiveFeedback():
        return Action(Action.ActionCode.POSITIVE_FEEDBACK)

    @staticmethod
    def NegativeFeedback():
        return Action(Action.ActionCode.NEGATIVE_FEEDBACK)

    @staticmethod
    def TutorialNextStep():
        return Action(Action.ActionCode.TUTORIAL_NEXT_STEP)

    @staticmethod
    def LoadScenario(scenario_data: str):
        return Action(Action.ActionCode.LOAD_SCENARIO, scenario_data=scenario_data)

    @staticmethod
    def NoopAction():
        return Action(Action.ActionCode.NONE)

    # Functions useful for action validation logic.
    @staticmethod
    def LeaderActions():
        return set(
            [
                Action.ActionCode.FORWARDS,
                Action.ActionCode.BACKWARDS,
                Action.ActionCode.TURN_LEFT,
                Action.ActionCode.TURN_RIGHT,
                Action.ActionCode.END_TURN,
                Action.ActionCode.SEND_INSTRUCTION,
            ]
        )

    @staticmethod
    def LeaderFeedbackActions():
        return set(
            [
                Action.ActionCode.POSITIVE_FEEDBACK,
                Action.ActionCode.NEGATIVE_FEEDBACK,
                Action.ActionCode.INTERRUPT,
            ]
        )

    @staticmethod
    def FollowerActions():
        return set(
            [
                Action.ActionCode.FORWARDS,
                Action.ActionCode.BACKWARDS,
                Action.ActionCode.TURN_LEFT,
                Action.ActionCode.TURN_RIGHT,
                Action.ActionCode.INSTRUCTION_DONE,
            ]
        )

    @staticmethod
    def SpectatorActions():
        return set(
            [
                Action.ActionCode.LOAD_SCENARIO,
            ]
        )

    @staticmethod
    def MovementActions():
        return set(
            [
                Action.ActionCode.FORWARDS,
                Action.ActionCode.BACKWARDS,
                Action.ActionCode.TURN_LEFT,
                Action.ActionCode.TURN_RIGHT,
            ]
        )

    @staticmethod
    def TutorialActions():
        return set(
            [
                Action.ActionCode.TUTORIAL_NEXT_STEP,
            ]
        )

    @staticmethod
    def RandomMovementAction():
        return Action(random.choice(list(Action.MovementActions())))

    # Define hash and eq comparison.
    def __hash__(self):
        return hash(self.action)

    def __eq__(self, other):
        return self.action == other.action

    @staticmethod
    def ActionMaskFromActor(actor, map):
        """Calculates an action mask for the given actor/map."""
        if actor.role() == Role.LEADER:
            actions = set(Action.LeaderActions())
        elif actor.role() == Role.FOLLOWER:
            actions = set(Action.FollowerActions())
        elif actor.role() == Role.SPECTATOR:
            actions = set(Action.SpectatorActions())
        else:
            raise ValueError("Invalid role: {}".format(actor.role))
        # Test forward collision.
        loc = actor.ProjectedLocation()
        forward = actor.ForwardLocation()
        if map.get_edge_between(loc, forward):
            actions.remove(Action.ActionCode.FORWARDS)

        # Test backward collision.
        backward = actor.BackwardLocation()
        if map.get_edge_between(loc, backward):
            actions.remove(Action.ActionCode.BACKWARDS)

        return Action.ActionMaskFromSet(actions)

    @staticmethod
    def ActionMaskFromSet(actions):
        mask = np.array([False] * Action.ActionCode.MAX.value)
        for action in actions:
            mask[action.value] = True
        return mask

    def __init__(self, action_code, instruction=None, i_uuid=None, scenario_data=None):
        if action_code == Action.ActionCode.SEND_INSTRUCTION:
            assert (
                instruction != None
            ), "Instruction must be provided for SEND_INSTRUCTION"
            if type(instruction) not in [str, bytes]:
                raise TypeError("Instruction must be a string or bytes")
            self.action = (action_code, instruction)
            return
        if action_code == Action.ActionCode.INSTRUCTION_DONE:
            assert i_uuid != None, "i_uuid must be provided for INSTRUCTION_DONE"
            if type(i_uuid) not in [str, bytes]:
                raise TypeError("i_uuid must be a string or bytes")
            self.action = (action_code, i_uuid)
            return
        if action_code == Action.ActionCode.LOAD_SCENARIO:
            assert (
                scenario_data != None
            ), "scenario_data must be provided for LOAD_SCENARIO"
            if type(scenario_data) not in [str, bytes]:
                raise TypeError("scenario_data must be a string or bytes")
            self.action = (action_code, scenario_data)
            return
        self.action = (action_code, None)

    def is_leader_action(self) -> bool:
        return self.action[0] in Action.LeaderActions()

    def is_follower_action(self) -> bool:
        return self.action[0] in Action.FollowerActions()

    def is_leader_feedback_action(self) -> bool:
        return self.action[0] in Action.LeaderFeedbackActions()

    def is_noop(self) -> bool:
        return self.action[0] == Action.ActionCode.NONE

    def is_end_turn(self) -> bool:
        return self.action[0] == Action.ActionCode.END_TURN

    def __str__(self):
        action_code = self.action[0]
        if action_code == Action.ActionCode.FORWARDS:
            return "FORWARDS"
        elif action_code == Action.ActionCode.BACKWARDS:
            return "BACKWARDS"
        elif action_code == Action.ActionCode.TURN_LEFT:
            return "TURN_LEFT"
        elif action_code == Action.ActionCode.TURN_RIGHT:
            return "TURN_RIGHT"
        elif action_code == Action.ActionCode.END_TURN:
            return "END_TURN"
        elif action_code == Action.ActionCode.INTERRUPT:
            return "INTERRUPT"
        elif action_code == Action.ActionCode.SEND_INSTRUCTION:
            return "SEND_INSTRUCTION: {}".format(self.action[1])
        elif action_code == Action.ActionCode.INSTRUCTION_DONE:
            return "INSTRUCTION_DONE: {}".format(self.action[1])
        if action_code == Action.ActionCode.POSITIVE_FEEDBACK:
            return "POSITIVE_FEEDBACK"
        elif action_code == Action.ActionCode.NEGATIVE_FEEDBACK:
            return "NEGATIVE_FEEDBACK"
        elif action_code == Action.ActionCode.TUTORIAL_NEXT_STEP:
            return "TUTORIAL_NEXT_STEP"
        elif action_code == Action.ActionCode.LOAD_SCENARIO:
            return "LOAD_SCENARIO"
        elif action_code == Action.ActionCode.NONE:
            return "NONE"
        else:
            return "INVALID"

    def action_code(self):
        return self.action[0]

    def message_to_server(self, actor):
        action_code = self.action[0]
        action = None
        if action_code == Action.ActionCode.FORWARDS:
            action = actor.WalkForwardsAction()
        elif action_code == Action.ActionCode.BACKWARDS:
            action = actor.WalkBackwardsAction()
        elif action_code == Action.ActionCode.TURN_LEFT:
            action = actor.TurnLeftAction()
        elif action_code == Action.ActionCode.TURN_RIGHT:
            action = actor.TurnRightAction()
        elif action_code == Action.ActionCode.END_TURN:
            return EndTurnMessage(), ""
        elif action_code == Action.ActionCode.INTERRUPT:
            return InterruptMessage(), ""
        elif action_code == Action.ActionCode.SEND_INSTRUCTION:
            return InstructionMessage(self.action[1]), ""
        elif action_code == Action.ActionCode.INSTRUCTION_DONE:
            return InstructionDoneMessage(self.action[1]), ""
        elif action_code == Action.ActionCode.TUTORIAL_NEXT_STEP:
            return TutorialNextStepMessage(), ""
        elif action_code == Action.ActionCode.NEGATIVE_FEEDBACK:
            return NegativeFeedbackMessage(), ""
        elif action_code == Action.ActionCode.POSITIVE_FEEDBACK:
            return PositiveFeedbackMessage(), ""
        elif action_code == Action.ActionCode.LOAD_SCENARIO:
            return LoadScenarioMessage(self.action[1]), ""
        else:
            return None, "Invalid lead action"
        assert action != None, "Invalid lead action"
        action_message = ActionsMessage([action])
        return action_message, ""


# client = Cb2Client(url)
# joined, reason = await client.Connect()
# assert joined, f"Could not join: {reason}"
# leader_agent = Agent(...)
# async with client.JoinGame(queue_type=LEADER_ONLY) as game:
#     observation, action_space = game.state()
#     action = await leader_agent.act(observation, action_space)
#     while not game.over():
#         observation, action_space = game.step(action)
#         action = leader_agent.act(observation, action_space)
class GameEndpoint(object):
    """A high-level interface to interact with a CB2 game.

    Do not initialize yourself. Use RemoteClient.JoinGame() or
    LocalGameCoordinator.JoinGame() instead. See remote_client.py and
    local_game_coordinator.py for examples.

    """

    def __init__(self, game_socket: GameSocket, config: Config, render=False):
        self.socket = game_socket
        self.config = config
        self.render = render
        self._timeout_observed = False
        self._reset()

    def _reset(self):
        self.last_step_call = datetime.now()
        self.map_update = None
        self.prop_update = None
        self.actors = {}
        self.cards = {}
        self.turn_state = None
        self.instructions = []
        self.queued_messages = []
        self.message_number = 0
        self.player_id = -1
        self._player_role = Role.NONE
        self.player_actor = None
        self._initial_state_ready = False
        self._initial_state_retrieved = False
        self._follower_moved = False
        self.live_feedback = None
        self.pygame_task = None
        self._timeout_observed = False
        self._tutorial_messages = []
        # Always create the display, even if render == None.
        # This lets the user access the the display object manually if they need.
        # It's a bit of a hack, because pygame can't render unless they're on the main thread.
        # So the user (on main thread) might want to manually access this and call draw().
        self.display = GameDisplay(SCREEN_SIZE)
        self.display.set_config(self.config)
        if self.render:
            logger.debug(f"Setting up display for rendering...")
            if self.pygame_task:
                self.pygame_task.cancel()
            loop = asyncio.get_event_loop()
            self.pygame_task = loop.create_task(pygame_event_handler())

    def visualization(self):
        return self.display

    def player_role(self):
        return self._player_role

    def actor_from_role(self, role):
        for actor_id in self.actors:
            actor = self.actors[actor_id]
            if actor.role() == role:
                return actor
        return None

    def initial_state(self):
        if self._initial_state_retrieved:
            logger.warning("Initial state already retrieved")
            return None
        if not self._initial_state_ready:
            logger.warning("Initial state not ready")
            return None
        self._initial_state_retrieved = True
        return self._state()

    def initialized(self):
        return self._initial_state_retrieved or self._initial_state_ready

    def timeout_occurred(self) -> bool:
        """Returns true if the game timed out in the last step()."""
        return self._timeout_observed

    def step(self, action, wait_for_turn=True) -> GameState:
        """Executes one action and blocks until the environment is ready for another action.

        For local games, we provide wait_for_turn as a parameter to disable
        blocking. Do NOT use for remote games.  This is hacky, but in short
        step() blocks until the game is ready for the next action for the
        player's role. If the follower calls this and ends their turn, then
        it will block until they receive a message from the leader. But that
        will never happen, because the leader will be blocked by the
        follower's step(). The long-term solution is to make step() return
        if either role can act, and then rely on the user to call step()
        with an action from the correct agent (this will be verified).
        """
        # If too much time passes between calls to step(), log an error.
        if datetime.now() - self.last_step_call > timedelta(
            seconds=HEARTBEAT_TIMEOUT_S
        ):
            logger.warning(
                f"NOTE: Over {HEARTBEAT_TIMEOUT_S} seconds between calls to step(). Must call step more frequently than this, or the server will disconnect."
            )

        # Step() pseudocode:
        # Consume any pending actions. If the game state changes during any of these, return False rejecting the action.
        # Send action.
        # Send queued messages (like automated ping responses)
        # While it isn't our turn to move:
        #   Wait for tick
        #   Process messages
        # Return state
        #
        # Process any pending messages...
        self._timeout_observed = False
        if (not action.is_noop()) and not self._process_pending_messages():
            self._timeout_observed = True
            return self._state()
        valid_actions = set([])
        if self._player_role == Role.FOLLOWER:
            valid_actions = Action.FollowerActions()
            # noop is always valid
            valid_actions.add(Action.ActionCode.NONE)
        elif self._player_role == Role.LEADER:
            valid_actions = (
                Action.LeaderActions()
                if self.turn_state.turn == Role.LEADER
                else Action.LeaderFeedbackActions()
            )
            # noop is always valid
            valid_actions.add(Action.ActionCode.NONE)
        elif self._player_role == Role.SPECTATOR:
            # Spectators can only send a noop or load a scenario.
            valid_actions = Action.SpectatorActions()
        valid_actions.add(Action.ActionCode.NONE)
        for action_code in Action.TutorialActions():
            valid_actions.add(action_code)
        if action.action_code() not in valid_actions:
            raise ValueError(
                f"Player is role {self._player_role} and turn {self.turn_state.turn} but sent inappropriate action: {action}"
            )
        message, reason = action.message_to_server(self.player_actor)
        if message != None:
            logger.info(f"Sending action: {message.type}")
            self.socket.send_message(message)
        for message in self.queued_messages:
            logger.info(f"Sending action: {message.type}")
            self.socket.send_message(message)
        self.queued_messages = []
        # Reset this variable. We want to see if while waiting for ticks, the
        # follower has moved. This allows self._can_act() to return True if
        # playing as the leader, to give live feedback on a follower move.
        self._follower_moved = False
        # Call _wait_for_tick before checking _can_act(), to make sure we don't
        # miss any state transitions that took place on the server.
        waited, reason = self._wait_for_tick()
        if not waited:
            logger.warning(f"Issue waiting for tick: {reason}")
        if wait_for_turn:
            while not self._can_act() and not self.over() and self.socket.connected():
                waited, reason = self._wait_for_tick()
                if not waited:
                    logger.warning(f"Issue waiting for tick: {reason}")
                if self.render:
                    # Handle pygame events while waiting in between turns.
                    pygame_handle_events()
        state = self._state()
        # Clear internal live feedback before returning. This is to make sure that the
        # live feedback only occurs for 1 step per feedback message.
        self.live_feedback = None

        # Updates the game visualization. If self._render, draws the display to the screen.
        self._render()

        self.last_step_call = datetime.now()
        return state

    def _can_act(self):
        if self.player_role() == self.turn_state.turn:
            if self.player_role() == Role.FOLLOWER:
                # If we're out of movements, the turn is over. This temporary
                # state used to be emitted by the server. It has since been
                # fixed, but we still guard against it in the client.
                if self.turn_state.moves_remaining == 0:
                    return False
                # Check if there are active instructions.
                for instruction in self.instructions:
                    if not instruction.completed and not instruction.cancelled:
                        return True
                return False
            return True

        if (self.player_role() == Role.LEADER) and self.config.live_feedback_enabled:
            # Check if the follower position has changed since the last tick.
            return self._follower_moved

        if self.player_role() == Role.SPECTATOR:
            return True

        return False

    def _process_pending_messages(self) -> bool:
        """Process any pending messages from the server. Returns false if a turn change occurred. True if our turn never ended."""
        turn_change = False
        current_turn = self.turn_state.turn
        message, reason = self.socket.receive_message(
            timedelta(seconds=BLOCKING_ZERO_TIME)
        )
        while message:
            self._handle_message(message)
            if self.turn_state.turn != current_turn:
                turn_change = True
            message, reason = self.socket.receive_message(
                timedelta(seconds=BLOCKING_ZERO_TIME)
            )
        return not turn_change

    def _wait_for_tick(self, timeout=timedelta(seconds=60)):
        """Waits for a tick"""
        start_time = datetime.utcnow()
        end_time = start_time + timeout
        while not self.over() and self.socket.connected():
            if datetime.utcnow() > end_time:
                return False, "Timed out waiting for tick"
            message, reason = self.socket.receive_message(end_time - datetime.utcnow())
            if message is None:
                logger.warning(f"Received None from _receive_message. Reason: {reason}")
                continue
            self._handle_message(message)
            if message.type == message_from_server.MessageType.STATE_MACHINE_TICK:
                return True, ""
        # Game over, return True to exit without triggering any errors.
        return True, ""

    # Returns true if the game is over.
    def over(self):
        return self.turn_state.game_over or not self.socket.connected()

    def score(self):
        return self.turn_state.score

    def game_duration(self):
        return datetime.utcnow() - self.turn_state.game_start

    def action_mask(self):
        """Returns a mask of type np.ndarray filled with either 0 or -inf. Indicates which actions are currently valid."""
        if self.turn_state.turn != self.player_role():
            return Action.ActionMaskFromSet(set())
        return Action.ActionMaskFromActor(self.player_actor, self.map_update)

    def tutorial_messages(self):
        return self._tutorial_messages

    def __enter__(self):
        return self

    def close(self):
        if not self.over() and self.socket.connected():
            self.socket.send_message(LeaveMessage())
        if self.render:
            self.pygame_task.cancel()

    def __exit__(self, type, value, traceback):
        self.close()

    def _state(self) -> GameState:
        leader = None
        follower = None
        for id in self.actors:
            if self.actors[id].role() == Role.LEADER:
                leader = self.actors[id]
            elif self.actors[id].role() == Role.FOLLOWER:
                follower = self.actors[id]
        if leader is None or follower is None:
            logger.warning(f"One of leader/follower missing!")
        map_update = self.map_update
        props = self.cards.values()
        actors = []
        if leader is not None:
            actors.append(leader)
        if follower is not None:
            actors.append(follower)
        if self.player_role() == Role.FOLLOWER:
            map_update = CensorFollowerMap(map_update, follower, self.config)
            props = CensorFollowerProps(props, follower, self.config)
            actors = CensorActors(actors, follower, self.config)
        return GameState(
            map_update,
            props,
            self.turn_state,
            self.instructions,
            actors,
            self.live_feedback,
        )

    def Initialize(self, timeout=timedelta(seconds=60)):
        return self._initialize()

    def _initialize(self, timeout=timedelta(seconds=60)):
        """Initializes the game state.

        Initially, the game expects a certain number of messages to be sent. _initialize() blocks until these are received and then returns.
        """
        if self._initial_state_ready:
            logger.warning("Initial state already ready")
            return

        end_time = datetime.utcnow() + timeout
        logger.debug(f"Beginning INIT")
        while self.socket.connected():
            if datetime.utcnow() > end_time:
                raise Exception("Timed out waiting for game")
            response, reason = self.socket.receive_message(
                timeout=end_time - datetime.utcnow()
            )
            if response is None:
                logger.warning(
                    f"No message received from _receive_message(). Reason: {reason}"
                )
                continue
            if response.type == message_from_server.MessageType.STATE_SYNC:
                logger.debug(f"INIT received state sync.")
                state_sync = response.state
                self.player_id = state_sync.player_id
                self._player_role = state_sync.player_role
                for net_actor in state_sync.actors:
                    added_actor = actor.Actor(
                        net_actor.actor_id,
                        0,
                        net_actor.actor_role,
                        net_actor.location,
                        False,
                        net_actor.rotation_degrees,
                    )
                    self.actors[net_actor.actor_id] = added_actor
                    added_actor.add_action(
                        action_module.Init(
                            net_actor.actor_id,
                            net_actor.location,
                            net_actor.rotation_degrees,
                        )
                    )
                    while added_actor.has_actions():
                        added_actor.step()
                self.player_actor = self.actors[self.player_id]
                logger.debug(
                    f"Player start pos: {self.player_actor.location().to_offset_coordinates()}"
                )
                logger.debug(
                    f"Player start orientation: {self.player_actor.heading_degrees()}"
                )
            if response.type == message_from_server.MessageType.MAP_UPDATE:
                logger.debug(f"INIT received map")
                self.map_update = response.map_update
            if response.type == message_from_server.MessageType.PROP_UPDATE:
                logger.debug(f"INIT received prop")
                self._handle_prop_update(response.prop_update)
            if response.type == message_from_server.MessageType.GAME_STATE:
                logger.debug(f"INIT received turn state")
                self.turn_state = response.turn_state
                if self.over():
                    return False, "Game over"
            if response.type == message_from_server.MessageType.OBJECTIVE:
                logger.debug(f"INIT received objective")
                self.instructions = response.objectives
            if response.type == message_from_server.MessageType.STATE_MACHINE_TICK:
                logger.debug(f"Init TICK received")
                if None not in [
                    self.player_actor,
                    self.map_update,
                    self.prop_update,
                    self.turn_state,
                ]:
                    logger.debug(f"Init DONE for {self._player_role}")
                    self._initial_state_ready = True
                    if self.render:
                        self._render()
                    return True, ""
                else:
                    logger.warning(
                        f"Init not ready. Player role: {self._player_role}, map update: {self.map_update is not None}, prop update: {self.prop_update is not None}, turn state: {self.turn_state is not None}"
                    )
        return False, "Game initialization timed out."

    def _handle_prop_update(self, prop_update):
        self.prop_update = prop_update
        self.cards = {}
        for prop in prop_update.props:
            if prop.prop_type == PropType.CARD:
                self.cards[prop.id] = prop

    def _handle_state_sync(self, state_sync):
        """Handles a state sync message.

        Args:
            state_sync: The state sync message to handle.
        Returns:
            (bool, str): A tuple containing if the message was handled, and if not, the reason why.
        """
        for net_actor in state_sync.actors:
            if net_actor.actor_id not in self.actors:
                logger.error(
                    f"Received state sync for unknown actor {net_actor.actor_id}"
                )
                return
            actor = self.actors[net_actor.actor_id]
            if actor.role() == Role.FOLLOWER:
                if (
                    net_actor.location != actor.location()
                    or net_actor.rotation_degrees != actor.heading_degrees()
                ):
                    self._follower_moved = True
            while actor.has_actions():
                actor.drop()
            actor.add_action(
                action_module.Init(
                    net_actor.actor_id, net_actor.location, net_actor.rotation_degrees
                )
            )
            while actor.has_actions():
                actor.step()
            logger.debug(
                f"state sync for actor {net_actor.actor_id}. location: {actor.location().to_offset_coordinates()} rotation: {actor.heading_degrees()}"
            )

    def _handle_message(self, message):
        logger.debug(
            f"Received message type {message_from_server.MessageType(message.type)} from server"
        )
        if message.type == message_from_server.MessageType.ACTIONS:
            for action in message.actions:
                if action.id in self.actors:
                    actor = self.actors[action.id]
                    if actor.role() == Role.FOLLOWER:
                        self._follower_moved = True
                    actor.add_action(action)
                    while actor.has_actions():
                        actor.step()
                elif action.id in self.cards:
                    if action.action_type not in [ActionType.OUTLINE]:
                        logger.error(f"Received action for unknown prop: {action.id}")
                        continue
                    if action.border_radius <= 0.01:
                        prop_info = self.cards[action.id].prop_info
                        prop_info = dataclasses.replace(prop_info, border_radius=0)
                        card_info = self.cards[action.id].card_init
                        card_info = dataclasses.replace(card_info, selected=False)
                        self.cards[action.id] = dataclasses.replace(
                            self.cards[action.id],
                            prop_info=prop_info,
                            card_init=card_info,
                        )
                    else:
                        prop_info = self.cards[action.id].prop_info
                        prop_info = dataclasses.replace(
                            prop_info, border_radius=action.border_radius
                        )
                        card_info = self.cards[action.id].card_init
                        card_info = dataclasses.replace(card_info, selected=True)
                        self.cards[action.id] = dataclasses.replace(
                            self.cards[action.id],
                            prop_info=prop_info,
                            card_init=card_info,
                        )
                else:
                    logger.error(f"Received action for unknown actor: {action.id}")
        elif message.type == message_from_server.MessageType.STATE_SYNC:
            self._handle_state_sync(message.state)
        elif message.type == message_from_server.MessageType.GAME_STATE:
            self.turn_state = message.turn_state
        elif message.type == message_from_server.MessageType.MAP_UPDATE:
            logger.warning(
                f"Received map update after game started. This is unexpected."
            )
            self.map_update = message.map_update
        elif message.type == message_from_server.MessageType.OBJECTIVE:
            self.instructions = message.objectives
        elif message.type == message_from_server.MessageType.PING:
            self.queued_messages.append(PongMessage())
        elif message.type == message_from_server.MessageType.LIVE_FEEDBACK:
            self.live_feedback = message.live_feedback.signal
        elif message.type == message_from_server.MessageType.PROP_UPDATE:
            self._handle_prop_update(message.prop_update)
        elif message.type == message_from_server.MessageType.STATE_MACHINE_TICK:
            return
        elif message.type == message_from_server.MessageType.TUTORIAL_RESPONSE:
            self._tutorial_messages.append(message.tutorial_response)
        else:
            logger.warning(
                f"Received unexpected message type: {message.type}. msg: {message}"
            )

    def _render(self):
        if not self.render:
            return
        map_update, props, turn_state, instructions, actors, feedback = self._state()
        actor_states = [a.state() for a in actors]
        self.display.set_state_sync(
            state_sync.StateSync(
                len(actors), actor_states, self.player_id, self.player_role()
            )
        )
        self.display.set_props(props)
        self.display.set_map(map_update)
        self.display.set_instructions(instructions)
        self.display.draw()
        pygame.display.flip()

    def _generate_state_sync(self):
        actor_states = []
        for a in self.actors:
            actor_states.append(self.actors[a].state())
        role = self.player_role()
        return state_sync.StateSync(
            len(self.actors), actor_states, self.player_id, role
        )
