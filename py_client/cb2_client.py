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

class Cb2Client(object):
    class State(Enum):
        NONE = 0
        BEGIN = 1
        CONNECTED = 2
        IN_QUEUE = 3
        IN_GAME_INIT = 4 # In game, but the initial data like map & state haven't been received yet.
        GAME_STARTED = 6
        ERROR = 7
        MAX = 8

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
    
    def state(self):
        return self.init_state
    
    class QueueType(Enum):
        NONE = 0
        LEADER_ONLY = 1
        FOLLOWER_ONLY = 2
        DEFAULT = 3 # Could be assigned either leader or follower.
        MAX = 4
    async def EnterQueueAndWaitForGame(self, timeout=timedelta(minutes=6), queue_type=QueueType.DEFAULT):
        """ Enters the game queue and waits for a game.

            Waits for all of the following:
                - Server says the game has started
                - Server has sent a map update.
                - Server has sent a state sync.
                - Server has sent a prop update.
        
            Args:
                timeout: The maximum amount of time to wait for the game to start.
            Returns:
                (bool, str): A tuple containing if a game was joined, and if not, the reason why.
        """
        in_queue, reason = await self._join_queue(queue_type)
        if not in_queue:
            self.Reset()
            return False, f"Failed to join queue: {reason}"
        game_joined, reason = await self._wait_for_game(timeout)
        if not game_joined:
            self.Reset()
            return False, f"Failed to join game: {reason}"
        return True, ""

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
        if self.player_role != Role.LEADER:
            return False, "Not a leader, cannot send lead action"
        if action == Cb2Client.LeadActions.FORWARDS:
            await self._send_action(self.actor.WalkForwardsAction())
            self.actor.WalkForwards()
        elif action == Cb2Client.LeadActions.BACKWARDS:
            await self._send_action(self.actor.WalkBackwardsAction())
            self.actor.WalkBackwards()
        elif action == Cb2Client.LeadActions.TURN_LEFT:
            await self._send_action(self.actor.TurnLeftAction())
            self.actor.TurnLeft()
        elif action == Cb2Client.LeadActions.TURN_RIGHT:
            await self._send_action(self.actor.TurnRightAction())
            self.actor.TurnRight()
        elif action == Cb2Client.LeadActions.END_TURN:
            self._send_message(EndTurnMessage())
        elif action == Cb2Client.LeadActions.POSITIVE_FEEDBACK:
            self._send_message(PositiveFeedbackMessage())
        elif action == Cb2Client.LeadActions.NEGATIVE_FEEDBACK:
            self._send_message(NegativeFeedbackMessage())
        elif action == Cb2Client.LeadActions.INTERRUPT:
            self._send_message(InterruptMessage())
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
        if self.player_role != Role.LEADER:
            return False, "Not a leader, cannot send instruction"
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
        if self.player_role != Role.FOLLOWER:
            return False, "Not a follower, cannot send follow action"
    
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

    async def DoWhile(self, timeout, coroutine):
        """ Handles network messages while simultaneously doing a provided
        coroutine. Use this while taking blocking actions during your turn to
        prevent the game from desyncing.
        
            Args:
                timeout: The maximum amount of time to wait for the handler to finish.
                handler: The handler to run while waiting for messages.
            
            Returns:
                (bool, str): A tuple containing if the handler finished, and if not, the reason why.
        """
        task = asyncio.create_task(coroutine)
        try:
            timeout_end = datetime.now() + timeout
            while True:
                if datetime.now() > timeout_end:
                    return False, "Timeout"
                result, reason = self._drain_socket_message(timeout_end - datetime.now())
                if not result:
                    return False, f"Encountered while draining socket: {reason}"
                if task.done():
                    return True, ""
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.warning(f"Task {task} cancelled")

    async def _drain_socket_coroutine(self, timeout):
        timeout_end = datetime.now() + timeout
        done_waiting = False
        while not done_waiting:
            if datetime.now() > timeout_end:
                return False, "Timeout"
            result, reason = await self._drain_socket_message(timeout_end - datetime.now())
            if not result:
                return False, f"Encountered while draining socket: {reason}"

    async def _send_queued_messages(self):
        if self.init_state != Cb2Client.State.GAME_STARTED:
            logger.error(f"_send_queued_messages called when not in game")
            return
        if len(self.queued_messages) == 0:
            return
        for message in self.queued_messages:
            await self._send_message(message)
        self.queued_messages = []

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
    
    def _game_initial_data_received(self):
        return (
            self.map_update is not None and
            self.state_sync is not None and
            self.prop_update is not None and
            self.turn_state is not None
        )
    
    async def _send_message(self, message):
        """ Sends a message to the server.
        
            Args:
                message: The message to send.
        """
        binary_message = orjson.dumps(message, options=orjson.OPT_NAIVE_UTC)
        await self.ws.send_str(binary_message.decode('utf-8'))
    
    async def _send_action(self, action):
        """ Sends an action to the server.
        
            Args:
                action: The action to send.
        """
        message = message_to_server.ActionsFromServer([action])
        await self._send_message(message)
    
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
        self._handle_message(message_parsed)
        await self._send_queued_messages()
        return True, ""

    async def _join_queue(self, queue_type=QueueType.DEFAULT):
        """ Sends a join queue message to the server. """
        if self.init_state != Cb2Client.State.NONE:
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
            spawn_location = net_actor.location
            spawn_rotation = net_actor.rotation_degrees
            actor = self.actors[net_actor.actor_id]
            while actor.has_actions():
                actor.drop()
            actor.add_action(action.Init(net_actor.actor_id, spawn_location, spawn_rotation))

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
        player_role = None
        player_id = None
        start_time = datetime.utcnow()
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
                        print(f"Joined room. Role: {join_message.role}")
                        player_role = join_message.role
                        self.init_state = Cb2Client.State.IN_GAME_INIT
                    else:
                        print(f"Place in queue: {join_message.place_in_queue}")
                    if join_message.booted_from_queue == True:
                        print(f"Booted from queue!")
                        self.init_state = Cb2Client.State.CONNECTED
                        return False, "Booted from queue"
            if self.init_state == Cb2Client.State.IN_GAME_INIT and response.type == message_from_server.MessageType.STATE_SYNC:
                self.state_sync = response.state
            if self.init_state == Cb2Client.State.IN_GAME_INIT and response.type == message_from_server.MessageType.MAP_UPDATE:
                self.map_update = response.map_update
            if self.init_state == Cb2Client.State.IN_GAME_INIT and response.type == message_from_server.MessageType.PROP_UPDATE:
                self.prop_update = response.prop_update
            if self.init_state == Cb2Client.State.IN_GAME_INIT and response.type == message_from_server.MessageType.TURN_STATE:
                self.turn_state = response.turn_state
            if self.init_state == Cb2Client.State.IN_GAME_INIT and self._game_initial_data_received():
                self.init_state = Cb2Client.State.GAME_STARTED
                self.player_role = player_role
                self.player_id = player_id
                for actor in self.state_sync.actors:
                    spawn_location = actor.location
                    spawn_rotation = actor.rotation_degrees
                    if actor.id == self.player_id:
                        role = self.player_role
                    else:
                        if self.player_role == Role.LEADER:
                            role = Role.FOLLOWER
                        else:
                            role = Role.LEADER
                    self.actors[actor.actor_id] = actor.Actor(actor.actor_id, 0, role, spawn_location, spawn_rotation)
                    if actor.id == self.player_id:
                        self.actor = self.actors[actor.actor_id]
                return True, ""