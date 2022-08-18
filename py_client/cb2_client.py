from mimetypes import init
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

from client_messages import *
from server.hex import HecsCoord
from server.hex import HecsCoord
from server.messages import message_from_server
from server.messages import message_to_server
from server.messages import action
from server.messages import turn_state
from server.messages.objective import ObjectiveMessage
from server.messages.rooms import Role

logger = logging.getLogger(__name__)

class Player(object):
    def __init__(self, client, game, actor):
        self.game = game
        self.actor = actor
        self.client = client
    
    def role(self):
        return self.actor.role
    
    class LeadActions(Enum):
        NONE = 0
        FORWARDS = 1
        BACKWARDS = 2
        TURN_LEFT = 3
        TURN_RIGHT = 4
        END_TURN = 5
        POSITIVE_FEEDBACK = 6
        NEGATIVE_FEEDBACK = 7
        INTERRUPT = 8
        MAX = 9
    async def SendLeadAction(self, action):
        """ Sends a lead action to the server.

            TODO(sharf): implement turn checking -- certain actions happen
                during your turn and certain actions (live feedback) only happen
                during the other player's turn. Make sure this is enforced.
            
            Args:
                action: The LeadAction to send.
            Returns:
                (bool, str): A tuple containing if the action was sent, and if not, the reason why.
        """
        if self.role() != Role.LEADER:
            return False, "Not a leader, cannot send lead action"
        if action == Player.LeadActions.FORWARDS:
            await self._send_action(self.actor.WalkForwardsAction())
            self.actor.WalkForwards()
        elif action == Player.LeadActions.BACKWARDS:
            await self._send_action(self.actor.WalkBackwardsAction())
            self.actor.WalkBackwards()
        elif action == Player.LeadActions.TURN_LEFT:
            await self._send_action(self.actor.TurnLeftAction())
            self.actor.TurnLeft()
        elif action == Player.LeadActions.TURN_RIGHT:
            await self._send_action(self.actor.TurnRightAction())
            self.actor.TurnRight()
        elif action == Player.LeadActions.END_TURN:
            await self.client._send_message(EndTurnMessage())
        elif action == Player.LeadActions.POSITIVE_FEEDBACK:
            await self.client._send_message(PositiveFeedbackMessage())
        elif action == Player.LeadActions.NEGATIVE_FEEDBACK:
            await self.client._send_message(NegativeFeedbackMessage())
        elif action == Player.LeadActions.INTERRUPT:
            await self.client._send_message(InterruptMessage())
        else:
            return False, "Invalid lead action"
        return True, ""

    async def SendInstruction(self, instruction):
        """ Sends an instruction to the server.
        
            Args:
                instruction: The instruction to send. str-like object.
            Returns:
                (bool, str): A tuple containing if the instruction was sent, and if not, the reason why.
        """
        if self.role() != Role.LEADER:
            return False, "Not a leader, cannot send instruction"
        if self.game.turn_state.role != Role.LEADER:
            return False, "Not your turn, cannot send instruction"
        await self._send_message(InstructionMessage(instruction))
        return True, ""

    class FollowActions(Enum):
        NONE = 0
        FORWARDS = 1
        BACKWARDS = 2
        TURN_LEFT = 3
        TURN_RIGHT = 4
        INSTRUCTION_DONE = 5
        MAX = 6
    async def SendFollowAction(self, action):
        """  Sends a follow action to the server.
        
            Args:
                action: The FollowAction to send.
            Returns:
                (bool, str): A tuple containing if the action was sent, and if not, the reason why.
        """
        if self.role() != Role.FOLLOWER:
            return False, "Not a follower, cannot send follow action"
        if self.game.turn_state.role != Role.FOLLOWER:
            return False, "Not your turn, cannot send follow action"
        if action == Player.FollowActions.FORWARDS:
            await self._send_action(self.actor.WalkForwardsAction())
            self.actor.WalkForwards()
        elif action == Player.FollowActions.BACKWARDS:
            await self._send_action(self.actor.WalkBackwardsAction())
            self.actor.WalkBackwards()
        elif action == Player.FollowActions.TURN_LEFT:
            await self._send_action(self.actor.TurnLeftAction())
            self.actor.TurnLeft()
        elif action == Player.FollowActions.TURN_RIGHT:
            await self._send_action(self.actor.TurnRightAction())
            self.actor.TurnRight()
        elif action == Player.FollowActions.INSTRUCTION_DONE:
            objectives = self.game.objectives
            first_objective = None
            for objective in objectives:
                if not objective.completed and not objective.cancelled:
                    first_objective = objective
                    break
            if first_objective is None:
                return False, "No objectives to complete"
            await self.client._send_message(InstructionDoneMessage(first_objective.uuid))
        else:
            return False, f"Invalid follow action: {action}"
        return True, ""

    async def _send_action(self, action):
        """ Sends an action to the server.
        
            Args:
                action: The action to send.
        """
        message = message_to_server.ActionsFromServer([action])
        await self._send_message(message)


# object that gives access to game (map, actors, state, instructions, etc).
# It gets those things from calls from cb2client.
# works with context manager and async coroutine so you can do something like:

# client.Connect(url)
# async with client.JoinGame(queue_type) as game:
#     while not game.over():
#        game.state()
#        game.turn()
# 
# and JoinGame() starts a coroutine which updates game state in the background.
class Game(object):
    def __init__(self, client):
        self.client = client
        self.Reset()

    def Reset(self):
        self.map_update = None
        self.prop_update = None
        self.actor = None
        self.actors = {}
        self.queued_messages = []
        self.turn_state = None
        self.leader = None
        self.follower = None
    
    def Leader(self):
        for actor in self.actors:
            if actor.role == Role.LEADER:
                return actor
        return None

    def Follower(self):
        for actor in self.actors:
            if actor.role == Role.FOLLOWER:
                return actor
        return None
    
    # Returns true if the game is over.
    def over(self):
        return self.turn_state.game_over
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, type, value, traceback):
        self.client.Reset()
    
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

    async def Connect(self):
        """ Connect to the server.

            Returns:
                (bool, str): True if connected. If not, the second element is an error message.
        """
        if self.init_state != Cb2Client.State.NONE:
            return False, "Server is not in the BEGIN state. Call Reset() first?"
        url = f"{self.url}/player_endpoint"
        logger.info(f"Connecting to {url}...")
        session = aiohttp.ClientSession()
        ws = await session.ws_connect(url)
        logger.info(f"Connected!")
        self.session = session
        self.ws = ws
        self.init_state = Cb2Client.State.CONNECTED
        return True, ""
    
    async def Reset(self):
        if self.session is not None:
            await self.session.close()
        if self.ws is not None:
            await self.ws.close()
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
    async def JoinGame(self, timeout=timedelta(minutes=6), queue_type=QueueType.DEFAULT):
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
        in_queue, reason = await self._join_queue(queue_type)
        if not in_queue:
            self.Reset()
            return None, f"Failed to join queue: {reason}"
        game_joined, reason = await self._wait_for_game(timeout)
        if not game_joined:
            self.Reset()
            return None, f"Failed to join game: {reason}"
        return self.game, ""
    
    
    async def WaitForTurn(self, timeout=timedelta(minutes=5)):
        """ Waits for it to be our turn.

            Args:
                timeout: The maximum amount of time to wait for our turn.
            Returns:
                (bool, str): A tuple containing if it is our turn, and if not, the reason why.
        """
        # Make sure we've joined a game.
        if self.state < Cb2Client.State.GAME_STARTED:
            return False, "Not in game"
        # Check if its currently our turn and return immediately.
        if self.turn_state.role == self.player_role:
            return True, ""
        timeout_end = datetime.now() + timeout
        while True:
            if datetime.now() > timeout_end:
                return False, "Timeout"
            result, reason = self._drain_socket_message(timeout_end - datetime.now())
            if not result:
                return False, f"Encountered while draining socket: {reason}"
            if self.turn_state.role == self.player_role:
                return True, ""

    async def _send_queued_messages(self):
        if self.init_state != Cb2Client.State.GAME_STARTED:
            logger.error(f"_send_queued_messages called when not in game")
            return
        if len(self.queued_messages) == 0:
            return
        for message in self.queued_messages:
            await self._send_message(message)
        self.queued_messages = []
    
    async def _send_message(self, message):
        """ Sends a message to the server.
        
            Args:
                message: The message to send.
        """
        binary_message = orjson.dumps(message, options=orjson.OPT_NAIVE_UTC)
        await self.ws.send_str(binary_message.decode('utf-8'))
    
    async def _cb2_task(self):
        # Make sure we've joined a game.
        if self.state < Cb2Client.State.GAME_STARTED:
            return False, "Not in game"
        while True:
            result, reason = await self._drain_socket_message(timedelta(minutes=5))
            if not result:
                return False, f"Encountered while draining socket: {reason}"
    
    async def _drain_socket_message(self, timeout):
        if self.ws.closed:
            return False, "Socket closed."
        try:
            message = await self.ws.receive(timeout=timeout)
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
        await self._send_queued_messages()
        return True, ""

    async def _join_queue(self, queue_type=QueueType.DEFAULT):
        """ Sends a join queue message to the server. """
        if self.init_state not in [Cb2Client.State.BEGIN, Cb2Client.State.GAME_OVER, Cb2Client.State.ERROR]:
            return False, "Already in game"
        if queue_type == Cb2Client.QueueType.DEFAULT:
            await self._send_message(JoinQueueMessage())
        elif queue_type == Cb2Client.QueueType.LEADER_ONLY:
            await self._send_message(JoinLeaderQueueMessage())
        elif queue_type == Cb2Client.QueueType.FOLLOWER_ONLY:
            await self._send_message(JoinFollowerQueueMessage())
        else:
            return False, f"Invalid queue type {queue_type}"
        self.init_state = Cb2Client.State.IN_QUEUE
        return True, ""
    
    async def _wait_for_game(self, timeout=timedelta(minutes=6)):
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
            message = await self.ws.receive()
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