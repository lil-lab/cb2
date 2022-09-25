import aiohttp
import asyncio
import fire
import logging
import nest_asyncio
import orjson
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
from py_client.game_endpoint import GameEndpoint
from py_client.game_socket import GameSocket
from py_client.follower_data_masking import CensorFollowerMap, CensorFollowerProps, CensorActors
from server.hex import HecsCoord
from server.main import HEARTBEAT_TIMEOUT_S
from server.config.config import Config
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

# This page defines and implements the CB2 headless client API.
# Here is an example of how to use the API:
#
# client = RemoteClient(url)
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


class RemoteSocket(GameSocket):
    def __init__(self, client):
        self.client = client
    
    def send_message(self, message: message_to_server.MessageToServer):
        """ Send a message to the server. Blocking. """
        self.client._send_message(message)
    
    def connected(self) -> bool:
        """ Is the socket connected to a server or state machine? """
        return self.client.connected()
    
    def receive_message(self, timeout: timedelta) -> message_from_server.MessageFromServer:
        """ Blocks until a message is received or the timeout is reached. """
        return self.client._receive_message(timeout)


# Client which manages connection state and shuffling of messages to Game
# object. See the comment at the top of this file for an example usage.
class RemoteClient(object):
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

        # Detect if we're running in an interactive shell and warn the user about the server heartbeat timeout.
        if hasattr(sys, 'ps1'):
            logger.warn(f"NOTE: You're running in an interactive shell. The server will disconnect you after {HEARTBEAT_TIMEOUT_S} seconds (by default) of inactivity. Remain active by calling Game.step(). For this reason, it's recommended not to use this library manually from a REPL loop.")
    
    def Connect(self):
        """ Connect to the server.

            Returns:
                (bool, str): True if connected. If not, the second element is an error message.
        """
        if self.init_state != RemoteClient.State.BEGIN:
            return False, "Server is not in the BEGIN state. Call Reset() first?"
        config_url = f"{self.url}/data/config"
        config_response = requests.get(config_url)
        if config_response.status_code != 200:
            return False, f"Could not get config from {config_url}: {config_response.status_code}"
        self.config = Config.from_json(config_response.text)
        url = f"{self.url}/player_endpoint"
        logger.info(f"Connecting to {url}...")
        session = aiohttp.ClientSession()
        ws = self.event_loop.run_until_complete(session.ws_connect(url))
        logger.info(f"Connected!")
        self.session = session
        self.ws = ws
        self.init_state = RemoteClient.State.CONNECTED
        return True, ""
    
    def connected(self):
        return self.init_state in [
            RemoteClient.State.CONNECTED,
            RemoteClient.State.IN_QUEUE,
            RemoteClient.State.IN_GAME_INIT,
            RemoteClient.State.GAME_STARTED,
            RemoteClient.State.GAME_OVER
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
        self.init_state = RemoteClient.State.BEGIN
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
    def JoinGame(self, timeout=timedelta(minutes=6), queue_type=QueueType.DEFAULT, i_uuid: str = ""):
        """ Enters the game queue and waits for a game.

            Waits for all of the following:
                - Server says the game has started
                - Server has sent a map update.
                - Server has sent a state sync.
                - Server has sent a prop update.
        
            Args:
                timeout: The maximum amount of time to wait for the game to start.
                queue_type: Which queue to join (DEFAULT, LEADER_ONLY, FOLLOWER_ONLY).
                i_uuid: Instruction UUID to resume from. Empty implies new game.
            Returns:
                (Game, str): The game that was started. If the game didn't start, the second element is an error message.
            Raises:
                TimeoutError: If the game did not start within the timeout.
        """
        in_queue, reason = self._join_queue(queue_type, i_uuid)
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
            self.init_state = RemoteClient.State.ERROR
        except ConnectionResetError as e:
            logger.error(f"Connection reset: {e}")
            self.init_state = RemoteClient.State.CONNECTED
    
    def _join_queue(self, queue_type=QueueType.DEFAULT, i_uuid: str = ""):
        """ Sends a join queue message to the server. """
        if self.init_state not in [RemoteClient.State.CONNECTED, RemoteClient.State.GAME_OVER]:
            return False, f"Not ready to join game. State: {str(self.init_state)}"
        if queue_type == RemoteClient.QueueType.DEFAULT:
            self._send_message(JoinQueueMessage(i_uuid))
        elif queue_type == RemoteClient.QueueType.LEADER_ONLY:
            self._send_message(JoinLeaderQueueMessage(i_uuid))
        elif queue_type == RemoteClient.QueueType.FOLLOWER_ONLY:
            self._send_message(JoinFollowerQueueMessage(i_uuid))
        else:
            return False, f"Invalid queue type {queue_type}"
        self.init_state = RemoteClient.State.IN_QUEUE
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
        if self.init_state != RemoteClient.State.IN_QUEUE:
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
            if self.init_state == RemoteClient.State.IN_QUEUE and response.type == message_from_server.MessageType.ROOM_MANAGEMENT:
                if response.room_management_response.type == messages.rooms.RoomResponseType.JOIN_RESPONSE:
                    join_message = response.room_management_response.join_response
                    if join_message.joined == True:
                        logger.info(f"Joined room. Role: {join_message.role}")
                        self.init_state = RemoteClient.State.IN_GAME_INIT
                        self.game = GameEndpoint(RemoteSocket(self), self.config, self.render)
                        result, reason = self.game._initialize(end_time - datetime.utcnow())
                        assert result, f"Failed to initialize game: {reason}"
                        self.init_state = RemoteClient.State.GAME_STARTED
                        return True, ""
                    else:
                        logger.info(f"Place in queue: {join_message.place_in_queue}")
                    if join_message.booted_from_queue == True:
                        logger.info(f"Booted from queue! Reason: {join_message.boot_reason}")
                        self.init_state = RemoteClient.State.CONNECTED
                        return False, f"Booted from queue! Reason: {join_message.boot_reason}"
        return False, "Disconnected"
    
    def _receive_message(self, timeout=timedelta(minutes=1)):
        message = self.event_loop.run_until_complete(self.ws.receive(timeout=timeout.total_seconds()))
        if message is None:
            return None, "None received from websocket.receive()"
        if message.type == aiohttp.WSMsgType.ERROR:
            return None, f"Received websocket error: {message.data}"
        if message.type == aiohttp.WSMsgType.CLOSED:
            self.init_state = RemoteClient.State.BEGIN
            return None, "Socket closed."
        if message.type == aiohttp.WSMsgType.CLOSE:
            self.init_state = RemoteClient.State.BEGIN
            return None, "Socket closing."
        if message.type != aiohttp.WSMsgType.TEXT:
            return None, f"Unexpected message type: {message.type}. data: {message.data}"
        response = message_from_server.MessageFromServer.from_json(message.data)
        return response, ""