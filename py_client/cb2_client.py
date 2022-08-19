import aiohttp
import asyncio
import fire
import logging
import orjson
import statistics as stats

import server.messages as messages
import server.actor as actor

from datetime import datetime
from datetime import timedelta
from enum import Enum

from py_client.client_messages import *
from server.hex import HecsCoord
from server.messages.action import Walk, Turn
from server.messages import message_from_server
from server.messages import message_to_server
from server.messages import action
from server.messages import turn_state
from server.messages.objective import ObjectiveMessage
from server.messages.rooms import Role

logger = logging.getLogger(__name__)

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
# 
# JoinGame() starts a coroutine which updates game state in the background.
#
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
            return InstructionMessage(instruction=self.action[1]), ""
        else:
            return None, "Invalid lead action"
        assert action != None, "Invalid lead action"
        actor.add_action(action)
        action_message = message_to_server.ActionsToServer([action])
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
        action = None
        if action == LeadFeedbackAction.ActionCode.POSITIVE_FEEDBACK:
            return PositiveFeedbackMessage(), ""
        elif action == LeadFeedbackAction.ActionCode.NEGATIVE_FEEDBACK:
            return NegativeFeedbackMessage(), ""
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
        action_message = message_to_server.ActionsToServer([action])
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
    def __init__(self, client):
        self.client = client
        self._reset()

    def _reset(self):
        self.map_update = None
        self.prop_update = None
        self.actor = None
        self.actors = {}
        self.turn_state = None
        self.instructions = []
        self.message_number = 0
        self.player_id = -1
        self.player_role = Role.NONE
    
    def player_role():
        return self.player_role
    
    def state(self):
        return self.map_update, self.prop_update, self.turn_state, self.instructions, self.actors
    
    def step(self, action):
        if isinstance(action, FollowAction):
            if self.player_role != Role.FOLLOWER:
                raise ValueError("Not a follower, cannot send follow action")
            if self.turn_state.role != Role.FOLLOWER:
                raise ValueError("Not your turn, cannot send follow action")
        if isinstance(action, LeadAction):
            if self.player_role != Role.LEADER:
                raise ValueError("Not a leader, cannot send lead action")
            if self.turn_state.role != Role.LEADER:
                raise ValueError("Not your turn, cannot send lead action")
        if isinstance(action, LeadFeedbackAction):
            if self.player_role != Role.LEADER:
                raise ValueError("Not a leader, cannot send lead feedback action")
            if self.turn_state.role != Role.FOLLOWER:
                raise ValueError("Not follower turn, cannot send lead feedback action")
        message, reason = action.message_to_server(self.actor)
        assert message != None, f"Invalid action: {reason}"
        asyncio.run(self.client._send_message(message_to_server))
        # Skips mirrored/loopback messages from server, which are just sent for verification.
        asyncio.run(self.client._drain_messages())
        return self.state()

    # Returns true if the game is over.
    def over(self):
        return self.turn_state.game_over
    
    async def __enter__(self):
        return self
    
    async def __exit__(self, type, value, traceback):
        if not self.over():
            asyncio.run(self.client._send_message(LeaveMessage()))
    
    def _initialize(self, state_sync, map, props, turn_state):
        self.map_update = map
        self.prop_update = props
        self.player_id = state_sync.player_id
        self.player_role = state_sync.player_role
        for net_actor in state_sync.actors:
            self.actors[net_actor.id] = actor.Actor(net_actor.actor_id, 0, net_actor.actor_role, net_actor.location, False, net_actor.rotation_degrees)
        self.turn_state = turn_state
    
    def _handle_state_sync(self, state_sync):
        """ Handles a state sync message.
        
            Args:
                state_sync: The state sync message to handle.
            Returns:
                (bool, str): A tuple containing if the message was handled, and if not, the reason why.
        """
        for net_actor in self.state_sync.actors:
            if net_actor.actor_id not in self.actors:
                logger.error(f"Received state sync for unknown actor {net_actor.actor_id}")
                return False, "Received state sync for unknown actor"
            actor = self.actors[net_actor.actor_id]
            while actor.has_actions():
                actor.drop()
            actor.add_action(action.Init(
                net_actor.actor_id,
                actor.location,
                actor.rotation_degrees))

    def _handle_message(self, message):
        if message.type == message_from_server.MessageType.ACTIONS:
            for action in message.actions:
                if action.id == self.player_id:
                    # Skip actions that we made. These are just sent for confirmation.
                    continue
                if action.id not in self.actors:
                    logger.error(f"Received action for unknown actor: {action.id}")
                    continue
                self.actors[action.id].add_action(action)
        if message.type == message_from_server.MessageType.STATE_SYNC:
            self._handle_state_sync(message.state)
        if message.type == message_from_server.MessageType.GAME_STATE:
            self.turn_state = message.turn_state
        if message.type == message_from_server.MessageType.MAP_UPDATE:
            logger.warn(f"Received map update after game started. This is unexpected.")
            self.map_update = message.map_update
        if message.type == message_from_server.MessageType.OBJECTIVE:
            self.objectives = message.objectives
        if message.type == message_from_server.MessageType.PING:
            self.queued_messages.append(PongMessage())
        if message.type == message_from_server.MessageType.LIVE_FEEDBACK:
            self._live_feedback_handler(message.live_feedback.signal)
        else:
            logger.warn(f"Received unexpected message type: {message.type}")

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

    def __init__(self, url):
        self.session = None
        self.ws = None
        self.Reset()
        self.url = url

    def Connect(self):
        """ Connect to the server.

            Returns:
                (bool, str): True if connected. If not, the second element is an error message.
        """
        if self.init_state != Cb2Client.State.BEGIN:
            return False, "Server is not in the BEGIN state. Call Reset() first?"
        url = f"{self.url}/player_endpoint"
        logger.info(f"Connecting to {url}...")
        session = aiohttp.ClientSession()
        ws = asyncio.run(session.ws_connect(url))
        logger.info(f"Connected!")
        self.session = session
        self.ws = ws
        self.init_state = Cb2Client.State.CONNECTED
        return True, ""
    
    def Reset(self):
        if self.session is not None:
            asyncio.run(self.session.close())
        if self.ws is not None:
            asyncio.run(self.ws.close())
        self.session = None
        self.ws = None
        self.player_role = None
        self.player_id = -1
        self.init_state = Cb2Client.State.BEGIN
        self.map_update = None
        self.state_sync = None
        self.prop_update = None
        self.actor = None
        self.actors = {}
        self.queued_messages = []
        self.turn_state = None
        self.game = None
    
    def state(self):
        return self.init_state
    
    class QueueType(Enum):
        NONE = 0
        LEADER_ONLY = 1
        FOLLOWER_ONLY = 2
        DEFAULT = 3 # Could be assigned either leader or follower.
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
        binary_message = orjson.dumps(message, options=orjson.OPT_NAIVE_UTC)
        asyncio.run(self.ws.send_str(binary_message.decode('utf-8')))
    
    def _drain_socket_message(self, timeout):
        if self.ws.closed:
            return False, "Socket closed."
        try:
            message = asyncio.run(self.ws.receive(timeout=timeout))
        except Exception as e:
            return False, f"Failed to receive message due to: {e}"
        if message is None:
            return False, f"Received None from socket."
        if message.type == aiohttp.WSMsgType.ERROR:
            return False, f"Received error from socket: {message.data}"
        if message.type == aiohttp.WSMsgType.CLOSE:
            return False, f"WaitForTurn received close message."
        if message.type == aiohttp.WSMsgType.BINARY:
            return False, f"WaitForTurn received BINARY message."
        if message.type != aiohttp.WSMsgType.TEXT:
            logger.warn(f"wait_for_turn received unexpected message type: {message.type}. data: {message.data}. Ignoring")
            return True, ""
        message_parsed = message_from_server.MessageFromServer.from_json(message.data)
        if self.game == None:
            return False, f"Handling message when game is None: {message_parsed}"
        self.game._handle_message(message_parsed)
        return True, ""

    def _join_queue(self, queue_type=QueueType.DEFAULT):
        """ Sends a join queue message to the server. """
        if self.init_state not in [Cb2Client.State.BEGIN, Cb2Client.State.GAME_OVER, Cb2Client.State.ERROR]:
            return False, "Already in game"
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
        while True:
            if datetime.utcnow() > start_time + timeout:
                return False, "Timed out waiting for game"
            message = asyncio.run(self.ws.receive())
            if message is None:
                continue
            if message.type == aiohttp.WSMsgType.ERROR:
                print(f"Received error: {message.data}")
                continue
            if message.type != aiohttp.WSMsgType.TEXT:
                print(f"wait_for_join_messages received unexpected message type: {message.type}. data: {message.data}")
                continue
            response = message_from_server.MessageFromServer.from_json(message.data)
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
            if self.init_state == Cb2Client.State.IN_GAME_INIT and None not in [state_sync, map_update, prop_update, turn_state]:
                self.init_state = Cb2Client.State.GAME_STARTED
                self.game = Game(self)
                self.game._initialize(state_sync, map_update, prop_update, turn_state)
                return True, ""