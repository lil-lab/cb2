import aiohttp
import asyncio
import fire
import logging
import nest_asyncio
import orjson
import pygame
import requests
import statistics as stats
import sys

import server.messages as messages
import server.messages.state_sync as state_sync
import server.actor as actor

from datetime import datetime
from datetime import timedelta
from enum import Enum

from py_client.client_messages import *
from py_client.follower_data_masking import CensorFollowerMap, CensorFollowerProps, CensorActors
from server.hex import HecsCoord
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

# I dont' think I need this anymore. This is an attempt to export the Role symbol so that users of this package can access it.
Role = Role

# If render=True in the constructor for Cb2Client, this controls the resulting window size.
SCREEN_SIZE = 800

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

# This page defines and implements the CB2 headless client API.
# Here is an example of how to use the API:
#
# client = Cb2Client(url)
# joined, reason = client.Connect()
# assert joined, f"Could not join: {reason}"
# async with client.JoinGame(queue_type=leader_only) as game:
#     leader = game.leader()
#     while not game.over():
#        leader.WaitForTurn()
#        leader.SendLeadAction(Player.LeadActions.FORWARDS)
#        leader.SendLeadAction(Player.LeadActions.END_TURN)
#        game.follower().WaitForTurn()
#        leader.SendLeadAction(Player.LeadActions.POSITIVE_FEEDBACK)

# TODO(sharf): client.Connect() should have its own context manager, or at least
# make it so that __aexit__ for JoinGame() doesn't disconnect the client's
# socket.
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
class Game(object):
    def __init__(self, client, config, render=False):
        self.client = client
        self.config = config
        self.render = render
        if self.render:
            self.display = GameDisplay(SCREEN_SIZE)
            self.display.set_config(config)
        self._reset()

    def _reset(self):
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
        if self.render:
            loop = asyncio.get_event_loop()
            self.pygame_task = loop.create_task(pygame_event_handler())
    
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
    
    def step(self, action):
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
            self.client._send_message(message)
        for message in self.queued_messages:
            self.client._send_message(message)
        # Reset this variable. We want to see if while waiting for ticks, the
        # follower has moved. This allows self._can_act() to return True if
        # playing as the leader, to give live feedback on a follower move.
        self._follower_moved = False
        # Call _wait_for_tick before checking _can_act(), to make sure we don't
        # miss any state transitions that took place on the server.
        waited, reason = self._wait_for_tick()
        if not waited:
            logger.warn(f"Issue waiting for tick: {reason}")
        while not self._can_act() and not self.over() and self.client.connected():
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

        # If rendering is enabled, use the map visualizer to draw the game state.
        if self.render:
            self._render()

        return state
    
    def _can_act(self):
        if (self.player_role() == self.turn_state.turn):
            return True
        
        if ((self.player_role() == Role.LEADER) and self.config["live_feedback_enabled"]):
            # Check if the follower position has changed since the last tick.
            return self._follower_moved
        
        return False

    def _wait_for_tick(self, timeout=timedelta(seconds=60)):
        """ Waits for a tick """
        start_time = datetime.utcnow()
        end_time = start_time + timeout
        while not self.over() and self.client.connected():
            if datetime.utcnow() > end_time:
                return False, "Timed out waiting for tick"
            message, reason = self.client._receive_message(end_time - datetime.utcnow())
            if message is None:
                logger.warn(f"Received None from _receive_message. Reason: {reason}")
                continue
            self._handle_message(message)
            if message.type == message_from_server.MessageType.STATE_MACHINE_TICK:
                return True, ""
        return False, "Game over"

    # Returns true if the game is over.
    def over(self):
        return self.turn_state.game_over or not self.client.connected()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, value, traceback):
        if not self.over() and self.client.connected():
            self.client._send_message(LeaveMessage())
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
    
    def _initialize(self, state_sync, map, props, turn_state):
        if self._initial_state_ready:
            logger.warn("Initial state already ready")
            return
        self.map_update = map
        self._handle_prop_update(props)
        self.player_id = state_sync.player_id
        self._player_role = state_sync.player_role
        for net_actor in state_sync.actors:
            self.actors[net_actor.actor_id] = actor.Actor(net_actor.actor_id, 0, net_actor.actor_role, net_actor.location, False, net_actor.rotation_degrees)
        self.player_actor = self.actors[self.player_id]
        self.turn_state = turn_state
        self._initial_state_ready = True
        if self.render:
            self._render()
    
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
            self.live_feedback = message.live_feedback
        elif message.type == message_from_server.MessageType.PROP_UPDATE:
            self._handle_prop_update(message.prop_update)
        elif message.type == message_from_server.MessageType.STATE_MACHINE_TICK:
            return
        else:
            logger.warn(f"Received unexpected message type: {message.type}")
    
    def _render(self):
        if self.render:
            map_update, props, turn_state, instructions, actors, feedback = self._state()
            actor_states = [a.state() for a in actors]
            self.display.set_state_sync(state_sync.StateSync(len(actors), actor_states, self.player_id, self.player_role()))
            self.display.set_props(props)
            self.display.set_map(map_update)
            self.display.draw()
            pygame.display.flip()
    
    def _generate_state_sync(self):
        actor_states = []
        for a in self.actors:
            actor_states.append(self.actors[a].state())
        role = self.player_role()
        return state_sync.StateSync(len(self.actors), actor_states, self.player_id, role)

# Client which manages connection state and shuffling of messages to Game
# object. See the comment at the top of this file for an example usage.
class Cb2Client(object):
    class State(Enum):
        NONE = 0
        BEGIN = 1
        CONNECTED = 2
        IN_QUEUE = 3
        IN_GAME_INIT = 4 # In game, but the initial data like map & state haven't been received yet.
        GAME_STARTED = 6
        GAME_OVER = 7
        ERROR = 8
        MAX = 9

    def __init__(self, url, render=False):
        """ Constructor.

            Args:
                url: (str) The URL of the server to connect to. Include http:// or https://!
                render: (bool) Whether to render the game using pygame, for the user to see.
        """
        self.session = None
        self.ws = None
        self.render = render # Whether to render the game with pygame.
        self.Reset()
        self.url = url
        self.event_loop = asyncio.get_event_loop()
        logging.basicConfig(level=logging.INFO)
        # Lets us synchronously block on an event loop that's already running.
        # This means we can encapsulate asyncio without making our users learn
        # how to use await/async. This isn't technically needed, unless you want
        # to be compatible with something like jupyter or anything else which
        # requires an always-running event loop.
        nest_asyncio.apply()
    
    def Connect(self):
        """ Connect to the server.

            Returns:
                (bool, str): True if connected. If not, the second element is an error message.
        """
        if self.init_state != Cb2Client.State.BEGIN:
            return False, "Server is not in the BEGIN state. Call Reset() first?"
        config_url = f"{self.url}/data/config"
        config_response = requests.get(config_url)
        if config_response.status_code != 200:
            return False, f"Could not get config from {config_url}: {config_response.status_code}"
        self.config = config_response.json()
        url = f"{self.url}/player_endpoint"
        logger.info(f"Connecting to {url}...")
        session = aiohttp.ClientSession()
        ws = self.event_loop.run_until_complete(session.ws_connect(url))
        logger.info(f"Connected!")
        self.session = session
        self.ws = ws
        self.init_state = Cb2Client.State.CONNECTED
        return True, ""
    
    def connected(self):
        return self.init_state in [
            Cb2Client.State.CONNECTED,
            Cb2Client.State.IN_QUEUE,
            Cb2Client.State.IN_GAME_INIT,
            Cb2Client.State.GAME_STARTED,
            Cb2Client.State.GAME_OVER
        ]
        
    def Reset(self):
        if self.session is not None:
            self.event_loop.run_until_complete(self.session.close())
        if self.ws is not None:
            self.event_loop.run_until_complete(self.ws.close())
        self.session = None
        self.ws = None
        self.player_role = None
        self.player_id = -1
        self.init_state = Cb2Client.State.BEGIN
        self.map_update = None
        self.state_sync = None
        self.prop_update = None
        self.actors = {}
        self.turn_state = None
        self.game = None
        self.config = None
    
    def state(self):
        return self.init_state
    
    class QueueType(Enum):
        NONE = 0
        LEADER_ONLY = 1
        FOLLOWER_ONLY = 2
        DEFAULT = 3 # Could be assigned either leader or follower.asyncio.
        MAX = 4
    def JoinGame(self, timeout=timedelta(minutes=6), queue_type=QueueType.DEFAULT):
        """ Enters the game queue and waits for a game.

            Waits for all of the following:
                - Server says the game has started
                - Server has sent a map update.
                - Server has sent a state sync.
                - Server has sent a prop update.
        
            Args:
                timeout: The maximum amount of time to wait for the game to start.
            Returns:
                (Game, str): The game that was started. If the game didn't start, the second element is an error message.
            Raises:
                TimeoutError: If the game did not start within the timeout.
        """
        in_queue, reason = self._join_queue(queue_type)
        assert in_queue, f"Failed to join queue: {reason}"
        game_joined, reason = self._wait_for_game(timeout)
        assert game_joined, f"Failed to join game: {reason}"
        return self.game
    
    def _send_message(self, message):
        """ Sends a message to the server.
        
            Args:
                message: The message to send.
        """
        if self.ws.closed:
            return
        if not self.connected():
            return
        try:
            binary_message = orjson.dumps(message, option=orjson.OPT_NAIVE_UTC | orjson.OPT_PASSTHROUGH_DATETIME, default=datetime.isoformat)
            self.event_loop.run_until_complete(self.ws.send_str(binary_message.decode('utf-8')))
        except RuntimeError as e:
            logger.error(f"Failed to send message: {e}")
            self.init_state = Cb2Client.State.ERROR
        except ConnectionResetError as e:
            logger.error(f"Connection reset: {e}")
            self.init_state = Cb2Client.State.CONNECTED
    
    def _join_queue(self, queue_type=QueueType.DEFAULT):
        """ Sends a join queue message to the server. """
        if self.init_state not in [Cb2Client.State.CONNECTED, Cb2Client.State.GAME_OVER]:
            return False, f"Not ready to join game. State: {str(self.init_state)}"
        if queue_type == Cb2Client.QueueType.DEFAULT:
            self._send_message(JoinQueueMessage())
        elif queue_type == Cb2Client.QueueType.LEADER_ONLY:
            self._send_message(JoinLeaderQueueMessage())
        elif queue_type == Cb2Client.QueueType.FOLLOWER_ONLY:
            self._send_message(JoinFollowerQueueMessage())
        else:
            return False, f"Invalid queue type {queue_type}"
        self.init_state = Cb2Client.State.IN_QUEUE
        return True, ""
    
    def _wait_for_game(self, timeout=timedelta(minutes=6)):
        """ Blocks until the game is started or a timeout is reached.

            Waits for all of the following:
                - Server says the game has started
                - Server has sent a map update.
                - Server has sent a state sync.
                - Server has sent a prop update.
                - Server has sent a turn state.
        
            Args:
                timeout: The maximum amount of time to wait for the game to start.
            Returns:
                (bool, str): A tuple containing if a game was joined, and if not, the reason why.
        """
        if self.init_state != Cb2Client.State.IN_QUEUE:
            return False, "Not in queue, yet waiting for game."
        start_time = datetime.utcnow()
        state_sync = None
        map_update = None
        prop_update = None
        turn_state = None
        end_time = start_time + timeout
        while self.connected():
            if datetime.utcnow() > end_time:
                return False, "Timed out waiting for game"
            response, reason = self._receive_message(timeout=end_time - datetime.utcnow())
            if response is None:
                logger.warn(f"No message received from _receive_message(). Reason: {reason}")
                continue
            if self.init_state == Cb2Client.State.IN_QUEUE and response.type == message_from_server.MessageType.ROOM_MANAGEMENT:
                if response.room_management_response.type == messages.rooms.RoomResponseType.JOIN_RESPONSE:
                    join_message = response.room_management_response.join_response
                    if join_message.joined == True:
                        logger.info(f"Joined room. Role: {join_message.role}")
                        self.init_state = Cb2Client.State.IN_GAME_INIT
                    else:
                        logger.info(f"Place in queue: {join_message.place_in_queue}")
                    if join_message.booted_from_queue == True:
                        logger.info(f"Booted from queue!")
                        self.init_state = Cb2Client.State.CONNECTED
                        return False, "Booted from queue"
            if self.init_state == Cb2Client.State.IN_GAME_INIT and response.type == message_from_server.MessageType.STATE_SYNC:
                state_sync = response.state
            if self.init_state == Cb2Client.State.IN_GAME_INIT and response.type == message_from_server.MessageType.MAP_UPDATE:
                map_update = response.map_update
            if self.init_state == Cb2Client.State.IN_GAME_INIT and response.type == message_from_server.MessageType.PROP_UPDATE:
                prop_update = response.prop_update
            if self.init_state == Cb2Client.State.IN_GAME_INIT and response.type == message_from_server.MessageType.GAME_STATE:
                turn_state = response.turn_state
            if response.type == message_from_server.MessageType.STATE_MACHINE_TICK:
                if self.init_state == Cb2Client.State.IN_GAME_INIT and None not in [state_sync, map_update, prop_update, turn_state]:
                    self.init_state = Cb2Client.State.GAME_STARTED
                    self.game = Game(self, self.config, self.render)
                    self.game._initialize(state_sync, map_update, prop_update, turn_state)
                    return True, ""
        return False, "Disconnected"
    
    def _receive_message(self, timeout=timedelta(minutes=1)):
        message = self.event_loop.run_until_complete(self.ws.receive(timeout=timeout.total_seconds()))
        if message is None:
            return None, "None received from websocket.receive()"
        if message.type == aiohttp.WSMsgType.ERROR:
            return None, f"Received websocket error: {message.data}"
        if message.type == aiohttp.WSMsgType.CLOSED:
            self.init_state = Cb2Client.State.BEGIN
            return None, "Socket closed."
        if message.type == aiohttp.WSMsgType.CLOSE:
            self.init_state = Cb2Client.State.BEGIN
            return None, "Socket closing."
        if message.type != aiohttp.WSMsgType.TEXT:
            return None, f"Unexpected message type: {message.type}. data: {message.data}"
        response = message_from_server.MessageFromServer.from_json(message.data)
        return response, ""