""" This file defines a high-level API for interacting with a CB2 game. It is
intended to be used for developers creating interactive bots that play CB2.
"""
import asyncio
import logging
import pygame
import sys

import server.messages as messages
import server.messages.state_sync as state_sync
import server.actor as actor

from datetime import datetime
from datetime import timedelta
from enum import Enum

from py_client.client_messages import *
from py_client.follower_data_masking import CensorFollowerMap, CensorFollowerProps, CensorActors
from py_client.game_socket import GameSocket
from server.config.config import Config
from server.hex import HecsCoord
from server.main import HEARTBEAT_TIMEOUT_S
from server.messages.action import Action, CensorActionForFollower, Walk, Turn
from server.messages import message_from_server
from server.messages import message_to_server
from server.messages import action
from server.messages import turn_state
from server.messages.objective import ObjectiveMessage
from server.messages.prop import PropType
from server.messages.rooms import Role 
from server.map_tools.visualize import GameDisplay

logger = logging.getLogger(__name__)

# If render=True in the constructor for Game, this controls the resulting window size.
SCREEN_SIZE = 800

# I dont' think I need this anymore. This is an attempt to export the Role symbol so that users of this package can access it.
Role = Role

def pygame_handle_events():
    """ Checks if a key has been pressed and then exits the program. """
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit(0)

async def pygame_event_handler():
    """ Background task to handle pygame events.

    This is a coroutine. Recommended to start as an asyncio task and killed with
    task.Cancel().
    
    """
    while True:
        pygame_handle_events()
        await asyncio.sleep(0.1)

class LeadAction(object):
    class ActionCode(Enum):
        NONE = 0
        FORWARDS = 1
        BACKWARDS = 2
        TURN_LEFT = 3
        TURN_RIGHT = 4
        END_TURN = 5
        INTERRUPT = 6
        SEND_INSTRUCTION = 7
        MAX = 8

    def __init__(self, action_code, instruction=None):
        if action_code == LeadAction.ActionCode.SEND_INSTRUCTION:
            assert instruction != None, "Instruction must be provided for SEND_INSTRUCTION"
            if type(instruction) not in [str, bytes]:
                raise TypeError("Instruction must be a string or bytes")
        self.action = (action_code, instruction)
    
    def message_to_server(self, actor):
        action_code = self.action[0]
        action = None
        if action_code == LeadAction.ActionCode.FORWARDS:
            action = actor.WalkForwardsAction()
        elif action_code == LeadAction.ActionCode.BACKWARDS:
            action = actor.WalkBackwardsAction()
        elif action_code == LeadAction.ActionCode.TURN_LEFT:
            action = actor.TurnLeftAction()
        elif action_code == LeadAction.ActionCode.TURN_RIGHT:
            action = actor.TurnRightAction()
        elif action_code == LeadAction.ActionCode.END_TURN:
            return EndTurnMessage(), ""
        elif action_code == LeadAction.ActionCode.INTERRUPT:
            return InterruptMessage(), ""
        elif action_code == LeadAction.ActionCode.SEND_INSTRUCTION:
            return InstructionMessage(self.action[1]), ""
        else:
            return None, "Invalid lead action"
        assert action != None, "Invalid lead action"
        actor.add_action(action)
        actor.step()
        action_message = ActionsMessage([action])
        return action_message, ""


class LeadFeedbackAction(object):
    class ActionCode(Enum):
        NONE = 0
        POSITIVE_FEEDBACK = 1
        NEGATIVE_FEEDBACK = 2
        MAX = 3
    def __init__(self, action_code):
        self.action = action_code
    
    def message_to_server(self, actor):
        if self.action == LeadFeedbackAction.ActionCode.POSITIVE_FEEDBACK:
            return PositiveFeedbackMessage(), ""
        elif self.action == LeadFeedbackAction.ActionCode.NEGATIVE_FEEDBACK:
            return NegativeFeedbackMessage(), ""
        elif self.action == LeadFeedbackAction.ActionCode.NONE:
            return None, ""
        else:
            return None, "Invalid lead feedback action"

class FollowAction(object):
    class ActionCode(Enum):
        NONE = 0
        FORWARDS = 1
        BACKWARDS = 2
        TURN_LEFT = 3
        TURN_RIGHT = 4
        INSTRUCTION_DONE = 5
        MAX = 6

    def __init__(self, action_code, instruction_uuid=None):
        if action_code == FollowAction.ActionCode.INSTRUCTION_DONE:
            assert instruction_uuid != None, "Instruction UUID must be provided for INSTRUCTION_DONE"
        self.action = action_code, instruction_uuid

    def message_to_server(self, actor):
        action = None
        action_code = self.action[0]
        if action_code == FollowAction.ActionCode.FORWARDS:
            action = actor.WalkForwardsAction()
        elif action_code == FollowAction.ActionCode.BACKWARDS:
            action = actor.WalkBackwardsAction()
        elif action_code == FollowAction.ActionCode.TURN_LEFT:
            action = actor.TurnLeftAction()
        elif action_code == FollowAction.ActionCode.TURN_RIGHT:
            action = actor.TurnRightAction()
        elif action_code == FollowAction.ActionCode.INSTRUCTION_DONE:
            return InstructionDoneMessage(self.action[1]), ""
        else:
            return None, "Invalid follow action"
        assert action != None, "Invalid follow action"
        actor.add_action(action)
        actor.step()
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
    """ A high-level interface to interact with a CB2 game.

    Do not initialize yourself. Use RemoteClient.JoinGame() or
    LocalGameCoordinator.JoinGame() instead. See remote_client.py and
    local_game_coordinator.py for examples. 
    
    """
    def __init__(self, game_socket: GameSocket, config: Config, render=False):
        self.socket = game_socket
        self.config = config
        self.render = render
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
        # Always create the display, even if render == None.
        # This lets the user access the the display object manually if they need.
        # It's a bit of a hack, because pygame can't render unless they're on the main thread.
        # So the user (on main thread) might want to manually access this and call draw().
        self.display = GameDisplay(SCREEN_SIZE)
        self.display.set_config(self.config)
        if self.render:
            logger.info(f"Setting up display for rendering...")
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
            logger.warn("Initial state already retrieved")
            return None
        if not self._initial_state_ready:
            logger.warn("Initial state not ready")
            return None
        self._initial_state_retrieved = True
        return self._state()
    
    def step(self, action, wait_for_turn=True):
        """ Executes one action and blocks until the environment is ready for another action.
        
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
        if datetime.now() - self.last_step_call > timedelta(seconds=HEARTBEAT_TIMEOUT_S):
            logger.warn(f"NOTE: Over {HEARTBEAT_TIMEOUT_S} seconds between calls to step(). Must call step more frequently than this, or the server will disconnect.")

        # Step() pseudocode:
        # Send action.
        # Send queued messages (like automated ping responses)
        # While it isn't our turn to move:
        #   Wait for tick
        #   Process messages
        # Return
        if isinstance(action, FollowAction):
            if self._player_role != Role.FOLLOWER:
                raise ValueError("Not a follower, cannot send follow action")
            if self.turn_state.turn != Role.FOLLOWER and action.action[0] != FollowAction.ActionCode.NONE:
                raise ValueError(f"Not your turn, cannot send follow action: {action.action}")
        if isinstance(action, LeadAction):
            if self._player_role != Role.LEADER:
                raise ValueError("Not a leader, cannot send lead action")
            if self.turn_state.turn != Role.LEADER:
                raise ValueError("Not your turn, cannot send lead action")
        if isinstance(action, LeadFeedbackAction):
            if self._player_role != Role.LEADER:
                raise ValueError("Not a leader, cannot send lead feedback action")
            if self.turn_state.turn != Role.FOLLOWER:
                raise ValueError("Not follower turn, cannot send lead feedback action")
        message, reason = action.message_to_server(self.player_actor)
        if message != None:
            self.socket.send_message(message)
        for message in self.queued_messages:
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
            logger.warn(f"Issue waiting for tick: {reason}")
        if wait_for_turn:
            while not self._can_act() and not self.over() and self.socket.connected():
                waited, reason = self._wait_for_tick()
                if not waited:
                    logger.warn(f"Issue waiting for tick: {reason}")
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
        if (self.player_role() == self.turn_state.turn):
            if self.player_role() == Role.FOLLOWER:
                # Check if there are active instructions.
                for instruction in self.instructions:
                    if not instruction.completed and not instruction.cancelled:
                        return True
                return False
            return True
        else:
            logger.info(f"Role: {self.player_role()} Waiting for turn: {self.turn_state.turn}")
        
        if ((self.player_role() == Role.LEADER) and self.config.live_feedback_enabled):
            # Check if the follower position has changed since the last tick.
            return self._follower_moved
        
        return False

    def _wait_for_tick(self, timeout=timedelta(seconds=60)):
        """ Waits for a tick """
        start_time = datetime.utcnow()
        end_time = start_time + timeout
        while not self.over() and self.socket.connected():
            if datetime.utcnow() > end_time:
                return False, "Timed out waiting for tick"
            if self.player_role == Role.FOLLOWER:
                logger.info(f"FOLLOWER receive...")
            message, reason = self.socket.receive_message(end_time - datetime.utcnow())
            if self.player_role == Role.FOLLOWER:
                logger.info(f"FOLLOWER received message: {message}")
            if message is None:
                logger.warn(f"Received None from _receive_message. Reason: {reason}")
                continue
            self._handle_message(message)
            if message.type == message_from_server.MessageType.STATE_MACHINE_TICK:
                return True, ""
        return False, "Game over"

    # Returns true if the game is over.
    def over(self):
        return self.turn_state.game_over or not self.socket.connected()
    
    def score(self):
        return self.turn_state.score
    
    def game_duration(self):
        return (datetime.utcnow() - self.turn_state.game_start)
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, value, traceback):
        if not self.over() and self.socket.connected():
            self.socket.send_message(LeaveMessage())
        if self.render:
            self.pygame_task.cancel()

    def _state(self):
        leader = None
        follower = None
        for id in self.actors:
            if self.actors[id].role() == Role.LEADER:
                leader = self.actors[id]
            elif self.actors[id].role() == Role.FOLLOWER:
                follower = self.actors[id]
        if leader is None or follower is None:
            logger.warn(f"One of leader/follower missing!")
        map_update = self.map_update
        props = self.cards.values()
        actors = [leader, follower]
        if self.player_role() == Role.FOLLOWER:
            map_update = CensorFollowerMap(map_update, follower, self.config)
            props = CensorFollowerProps(props, follower, self.config)
            actors = CensorActors(actors, follower, self.config)
        return map_update, props, self.turn_state, self.instructions, actors, self.live_feedback
    
    def Initialize(self, timeout=timedelta(seconds=60)):
        return self._initialize()
    
    def _initialize(self, timeout=timedelta(seconds=60)):
        """ Initializes the game state. 

            Initially, the game expects a certain number of messages to be sent. _initialize() blocks until these are received and then returns.
        """
        if self._initial_state_ready:
            logger.warn("Initial state already ready")
            return
        
        end_time = datetime.utcnow() + timeout
        logger.info(f"Beginning INIT")
        while self.socket.connected():
            if datetime.utcnow() > end_time:
                raise Exception("Timed out waiting for game")
            response, reason = self.socket.receive_message(timeout=end_time - datetime.utcnow())
            if response is None:
                logger.warn(f"No message received from _receive_message(). Reason: {reason}")
                continue
            if response.type == message_from_server.MessageType.STATE_SYNC:
                logger.info(f"INIT received state sync.")
                state_sync = response.state
                self.player_id = state_sync.player_id
                self._player_role = state_sync.player_role
                for net_actor in state_sync.actors:
                    self.actors[net_actor.actor_id] = actor.Actor(net_actor.actor_id, 0, net_actor.actor_role, net_actor.location, False, net_actor.rotation_degrees)
                self.player_actor = self.actors[self.player_id]
            if response.type == message_from_server.MessageType.MAP_UPDATE:
                self.map_update = response.map_update
            if response.type == message_from_server.MessageType.PROP_UPDATE:
                logger.info(f"INIT received prop")
                self._handle_prop_update(response.prop_update)
            if response.type == message_from_server.MessageType.GAME_STATE:
                logger.info(f"INIT received turn state")
                self.turn_state = response.turn_state
                if self.over():
                    return False, "Game over"
            if response.type == message_from_server.MessageType.STATE_MACHINE_TICK:
                logger.info(f"Init TICK received")
                if None not in [self.player_actor, self.map_update, self.prop_update, self.turn_state]:
                    logger.info(f"Init DONE for {self._player_role}")
                    self._initial_state_ready = True
                    if self.render:
                        self._render()
                    return True, ""
                else:
                    logger.warn(f"Init not ready. Player role: {self._player_role}, map update: {self.map_update is not None}, prop update: {self.prop_update is not None}, turn state: {self.turn_state is not None}")
        return False, "Game initialization timed out."
    
    def _handle_prop_update(self, prop_update):
        self.prop_update = prop_update
        self.cards = {}
        for prop in prop_update.props:
            if prop.prop_type == PropType.CARD:
                self.cards[prop.id] = prop
    
    def _handle_state_sync(self, state_sync):
        """ Handles a state sync message.
        
            Args:
                state_sync: The state sync message to handle.
            Returns:
                (bool, str): A tuple containing if the message was handled, and if not, the reason why.
        """
        for net_actor in state_sync.actors:
            if net_actor.actor_id not in self.actors:
                logger.error(f"Received state sync for unknown actor {net_actor.actor_id}")
                return False, "Received state sync for unknown actor"
            actor = self.actors[net_actor.actor_id]
            if actor.role() == Role.FOLLOWER:
                if net_actor.location != actor.location() or net_actor.rotation_degrees != actor.heading_degrees():
                    self._follower_moved = True
            while actor.has_actions():
                actor.drop()
            actor.add_action(action.Init(
                net_actor.actor_id,
                net_actor.location,
                net_actor.rotation_degrees))
            while actor.has_actions():
                actor.step()
            logger.info(f"state sync for actor {net_actor.actor_id}. location: {actor.location().to_offset_coordinates()}")

    def _handle_message(self, message):
        if message.type == message_from_server.MessageType.ACTIONS:
            for action in message.actions:
                if action.id == self.player_id:
                    # Skip actions that we made. These are just sent for confirmation.
                    continue
                if action.id not in self.actors:
                    if action.id not in self.cards:
                        logger.error(f"Received action for unknown actor: {action.id}")
                    return
                actor = self.actors[action.id]
                if actor.role() == Role.FOLLOWER:
                    self._follower_moved = True
                actor.add_action(action)
                actor.step()
        elif message.type == message_from_server.MessageType.STATE_SYNC:
            self._handle_state_sync(message.state)
        elif message.type == message_from_server.MessageType.GAME_STATE:
            self.turn_state = message.turn_state
        elif message.type == message_from_server.MessageType.MAP_UPDATE:
            logger.warn(f"Received map update after game started. This is unexpected.")
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
        else:
            logger.warn(f"Received unexpected message type: {message.type}")
    
    def _render(self):
        map_update, props, turn_state, instructions, actors, feedback = self._state()
        actor_states = [a.state() for a in actors]
        self.display.set_state_sync(state_sync.StateSync(len(actors), actor_states, self.player_id, self.player_role()))
        self.display.set_props(props)
        self.display.set_map(map_update)
        self.display.set_instructions(instructions)
        if self.render:
            self.display.draw()
            pygame.display.flip()
    
    def _generate_state_sync(self):
        actor_states = []
        for a in self.actors:
            actor_states.append(self.actors[a].state())
        role = self.player_role()
        return state_sync.StateSync(len(self.actors), actor_states, self.player_id, role)
