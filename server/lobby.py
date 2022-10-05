from server.map_provider import CachedMapRetrieval
from server.messages.logs import GameInfo
from server.messages.rooms import Role
from server.messages.rooms import LeaveRoomNotice
from server.messages.rooms import JoinResponse
from server.messages.rooms import StatsResponse
from server.room import Room, RoomType
from server.messages.rooms import RoomRequestType
from server.messages.rooms import RoomManagementResponse
from server.messages.rooms import RoomResponseType
from server.messages.tutorials import RoleFromTutorialName 
from server.messages.tutorials import TutorialRequestType
from server.messages.tutorials import TutorialResponse
from server.messages.tutorials import TutorialResponseType
from server.remote_table import GetWorkerFromRemote
from server.schemas.mturk import Worker, WorkerQualLevel
from server.util import IdAssigner, GetCommitHash

from abc import ABC, abstractmethod
from aiohttp import web
from collections import deque
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime, timedelta
from queue import Queue
from typing import List, Tuple

import server.messages.message_from_server as message_from_server
import server.messages.message_to_server as message_to_server
import server.schemas.game as game_db

import asyncio
import logging
import orjson
import pathlib
import queue

logger = logging.getLogger(__name__)

@dataclass_json()
@dataclass(frozen=True)
class SocketInfo:
    room_id: int
    player_id: int
    role: Role

    def as_tuple(self):
        """ This is a bit of a hack, since it's sensitive to changes in the SocketInfo class.
        
            Reasons for doing this:
            - SocketInfo is relatively unchanged and small over a long period of time.
            - Dataclasses's astuple method is extremely inefficient (over half of stream_game_state execution time). This will save us 26us.
            - I have higher priority things to be doing than finding the best way to do this. It's not within the scope of this paper.
        """
        return (self.room_id, self.player_id, self.role)


""" This interface abstracts over different types of game lobbies.

    Lobbies manage a collection of games. They are responsible for creating new
    games, handling players joining and leaving games, matchmaking, and managing
    the game objects.

    Each lobby has 3 queues: Leader-only, Follower-only, and "either" (player
    queue). Additionally, each player may have a qualification or experience the
    lobby uses to determine their role in the game. For example, the mturk lobby
    (mturk_lobby.py) checks player experience from the database to determine
    which player is more experienced in the leader role.

    Lobbies exist to separate players by category. For example, a lobby might
    exist only for mturk workers or only for users who have been authenticated
    with Google SSO.

    The parent Lobby object has a matchmaking process and a room cleanup
    process. These must be launched with something like:
    
    ```
        tasks = asyncio.gather(lobby.matchmake(), lobby.cleanup_rooms(), ...)
        loop.run_until_complete(tasks)
    ```

    Or alternatively, depending on your usecase, `loop.create_task()` can be used.
"""
class Lobby(ABC):
    @abstractmethod
    def __init__(self, lobby_name):
        """ This class is abstract. Must call super().__init__() in subclasses. """
        self._lobby_name = lobby_name
        self._rooms = {}
        self._room_id_assigner = IdAssigner()
        self._remotes = {}  # {ws: SocketInfo}
        self._is_done = False
        self._player_queue = deque()
        self._follower_queue = deque()
        self._leader_queue = deque()
        self._base_log_directory = pathlib.Path("/dev/null")
        self._pending_room_management_responses = {}  # {ws: room_management_response}
        self._pending_tutorial_messages = {}  # {ws: tutorial_response}
        self._matchmaking_exc = None
    
    @abstractmethod
    def get_leader_follower_match(self) -> Tuple[web.WebSocketResponse, web.WebSocketResponse, str]:
        """ Returns a leader-follower match, or None if no match is available.

        Third return value is the instruction uuid to start the game from, if
        applicable. This is determined from UUIDs the clients may have
        requested.
        """
        ...

    def register_game_logging_directory(self, dir) -> None:
        """ Each lobby has its own log directory. Game logs are written to this directory. """
        self._base_log_directory = dir

    def player_queue(self) -> List[Tuple[(datetime, web.WebSocketResponse, str)]]:
        """ Query the player queue. 
        
            Returns a list of tuples of (queue_entry_time, websocket, instruction_uuid).
        """
        return self._player_queue

    def leader_queue(self) -> List[Tuple[(datetime, web.WebSocketResponse, str)]]:
        """ Query the leader queue. 
        
            Returns a list of tuples of (queue_entry_time, websocket, instruction_uuid).
        """
        return self._leader_queue
    
    def follower_queue(self) -> List[Tuple[(datetime, web.WebSocketResponse, str)]]:
        """ Query the follower queue. 
        
            Returns a list of tuples of (queue_entry_time, websocket, instruction_uuid).
        """
        return self._follower_queue

    def disconnect_socket(self, ws):
        """ This socket terminated its connection. End the game that the person was in."""
        self.remove_socket_from_queue(ws)
        if not ws in self._remotes:
            logging.info("Socket not found in self._remotes!")
            return
        room_id, player_id, _ = self._remotes[ws].as_tuple()
        if not room_id in self._rooms:
            # The room was already terminated by the other player.
            del self._remotes[ws]
            return
        self._rooms[room_id].remove_player(player_id, ws)
        # If a player leaves, the game ends for everyone in the room. Send them leave notices and end the game.
        for socket in self._rooms[room_id].player_endpoints():
            if not socket.closed:
                leave_notice = LeaveRoomNotice(
                    "Other player disconnected, game ending.")
                self._pending_room_management_responses[socket].put(
                    RoomManagementResponse(RoomResponseType.LEAVE_NOTICE, None, None, leave_notice))
                del self._remotes[socket]
        self._rooms[room_id].stop()
        del self._remotes[ws]
        del self._rooms[room_id]

    async def matchmake(self):
        """ Runs asyncronously, creating rooms for pending followers and
        leaders. """
        while not self._is_done:
            try:
                await asyncio.sleep(0.5)
                leader, follower, i_uuid = self.get_leader_follower_match()

                if (leader is None) or (follower is None):
                    continue

                logger.info(f"Creating room for {leader} and {follower}. Queue size: {len(self._player_queue)} Follower Queue: {len(self._follower_queue)}")

                if i_uuid is not None and i_uuid != "":
                    logger.info(f"Starting game from i_uuid: {i_uuid}")
                    # Start game from a specific point.
                    room = self.create_room(i_uuid, None, RoomType.PRESET_GAME, "", i_uuid)
                    if (room is None) or (not room.initialized()):
                        logger.warn(f"Error creating room from UUID {i_uuid}")
                        # Boot the leader & follower from the queue.
                        self._pending_room_management_responses[leader].put(
                            RoomManagementResponse(
                                RoomResponseType.JOIN_RESPONSE, None, 
                                JoinResponse(
                                    False, 0, Role.LEADER, True,
                                    "Could not create server from provided I_UUID"),
                                None, None))
                        self._pending_room_management_responses[follower].put(
                            RoomManagementResponse(
                                RoomResponseType.JOIN_RESPONSE, None, 
                                JoinResponse(
                                    False, 0, Role.FOLLOWER, True,
                                    "Could not create server from provided I_UUID"),
                                None, None))
                        continue
                    logger.info(f"Creating new game from instruction {room.name()}")
                    leader_id = room.add_player(leader, Role.LEADER)
                    follower_id = room.add_player(follower, Role.FOLLOWER)
                    self._remotes[leader] = SocketInfo(room.id(), leader_id, Role.LEADER)
                    self._remotes[follower] = SocketInfo(room.id(), follower_id, Role.FOLLOWER)
                    self._pending_room_management_responses[leader].put(
                        RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(True, 0, Role.LEADER), None, None))
                    self._pending_room_management_responses[follower].put(
                        RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(True, 0, Role.FOLLOWER), None, None))
                    continue

                # Setup room log directory.
                game_record = game_db.Game()
                game_record.save()
                game_id = game_record.id
                game_time = datetime.now().strftime("%Y-%m-%dT%Hh.%Mm.%Ss%z")
                game_name = f"{game_time}_{game_id}_GAME"
                log_directory = pathlib.Path(self._base_log_directory, game_name)
                log_directory.mkdir(parents=False, exist_ok=False)
                game_record.log_directory = str(log_directory)
                game_record.server_software_commit = GetCommitHash()
                game_record.save()

                # Create room.
                room = self.create_room(game_id, game_record)
                if room is None or not room.initialized():
                    logger.warn(f"Error creating room from UUID {i_uuid}")
                    # Boot the leader & follower from the queue.
                    self._pending_room_management_responses[leader].put(
                        RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, 0, Role.LEADER, True), None, None))
                    self._pending_room_management_responses[follower].put(
                        RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, 0, Role.FOLLOWER, True), None, None))
                    continue
                print("Creating new game " + room.name())
                leader_id = room.add_player(leader, Role.LEADER)
                follower_id = room.add_player(follower, Role.FOLLOWER)
                self._remotes[leader] = SocketInfo(room.id(), leader_id, Role.LEADER)
                self._remotes[follower] = SocketInfo(room.id(), follower_id, Role.FOLLOWER)

                game_info_path = pathlib.Path(log_directory, "game_info.jsonl.log")
                game_info_log = game_info_path.open("w")
                game_info = GameInfo(datetime.now(), game_id, game_name, [Role.LEADER, Role.FOLLOWER], [leader_id, follower_id])
                json_str = orjson.dumps(game_info, option=orjson.OPT_PASSTHROUGH_DATETIME, default=datetime.isoformat).decode('utf-8')
                game_info_log.write(json_str + "\n")
                game_info_log.close()

                self._pending_room_management_responses[leader].put(
                    RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(True, 0, Role.LEADER), None, None))
                self._pending_room_management_responses[follower].put(
                    RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(True, 0, Role.FOLLOWER), None, None))
            except Exception as e:
                logger.exception(e)
                self._matchmaking_exc = e

    def socket_in_room(self, ws):
        return ws in self._remotes

    def socket_info(self, ws):
        return self._remotes[ws] if ws in self._remotes else None

    def get_room(self, id):
        return self._rooms[id] if id in self._rooms else None

    def get_room_by_name(self, name):
        for room in self._rooms.values():
            if room.name == name:
                return room

    def room_ids(self):
        return self._rooms.keys()

    def end_server(self):
        for room in self._rooms.values():
            room.stop()
        self._is_done = True

    def create_room(self, id, game_record: game_db.Game,
                    type: RoomType = RoomType.GAME, tutorial_name: str = "", from_instruction : str = ""):
        """ 
            Creates a new room & starts an asyncio task to run the room's state machine.

            Returns the room, or None if startup failed. 
        """
        room = Room(
            # Room name.
            "Room #" + str(id) + ("(TUTORIAL)" if type == RoomType.TUTORIAL else ""),
            # Max number of players.
            2,
            # Room ID.
            id,
            game_record,
            type,
            tutorial_name,
            from_instruction)
        if not room.initialized():
            return None
        self._rooms[id] = room
        self._rooms[id].start()
        return self._rooms[id]

    def delete_unused_rooms(self):
        rooms = list(self._rooms.values())
        for room in rooms:
            if room.done() and not room.has_pending_messages():
                logger.info(f"Deleting unused room: {room.name()}")
                self.delete_room(room.id())

    def delete_room(self, id):
        self._rooms[id].stop()
        player_endpoints = list(self._rooms[id].player_endpoints())
        for ws in player_endpoints:
            room_id, player_id, _ = self._remotes[ws].as_tuple()
            self._rooms[id].remove_player(player_id, ws)
            del self._remotes[ws]    
        del self._rooms[id]

    def available_room_id(self):
        for room_id in self._rooms.keys():
            if not self._rooms[room_id].is_full():
                return room_id
        return None
    
    async def cleanup_rooms(self):
        while not self._is_done:
            await asyncio.sleep(2)
            self.delete_unused_rooms()
    
    def create_tutorial(self, player, tutorial_name):
        logger.info(f"Creating tutorial room for {player}.")

        # Setup room log directory.
        game_record = game_db.Game()
        game_record.save()
        game_id = game_record.id
        game_time = datetime.now().strftime("%Y-%m-%dT%Hh.%Mm.%Ss%z")
        game_name = f"{game_time}_{game_id}_TUTORIAL"
        log_directory = pathlib.Path(self._base_log_directory, game_name)
        log_directory.mkdir(parents=False, exist_ok=False)
        game_record.log_directory = str(log_directory)
        game_record.server_software_commit = GetCommitHash()
        game_record.save()

        # Create room.
        room = self.create_room(game_id, game_record, RoomType.TUTORIAL, tutorial_name)
        if room == None:
            return None
        print("Creating new tutorial room " + room.name())
        role = RoleFromTutorialName(tutorial_name)
        player_id = room.add_player(player, role)
        self._remotes[player] = SocketInfo(room.id(), player_id, role)

        game_info_path = pathlib.Path(log_directory, "game_info.jsonl.log")
        game_info_log = game_info_path.open("w")
        game_info = GameInfo(datetime.now(), game_id, game_name, [role], [player_id])
        json_str = orjson.dumps(game_info, option=orjson.OPT_PASSTHROUGH_DATETIME, default=datetime.isoformat).decode('utf-8')
        game_info_log.write(json_str + "\n")
        game_info_log.close()
        return room

    def handle_tutorial_request(self, tutorial_request, ws):
        if ws not in self._pending_tutorial_messages:
            self._pending_tutorial_messages[ws] = Queue()
        if tutorial_request.type == TutorialRequestType.START_TUTORIAL:
            room = self.create_tutorial(ws, tutorial_request.tutorial_name)
            self._pending_tutorial_messages[ws].put(
                TutorialResponse(TutorialResponseType.STARTED, tutorial_request.tutorial_name, None, None))
        else:
            logger.warning(f'Room manager received incorrect tutorial request type {tutorial_request.type}.')
    
    def join_player_queue(self, ws, instruction_uuid=""):
        if ws in self._player_queue:
            logger.info(f"Join request is from socket which is already in the wait queue. Ignoring.")
            return
        if ws in self._follower_queue:
            logger.info(f"Join request is from socket which is already in the follow wait queue. Ignoring.")
            return
        if ws in self._leader_queue:
            logger.info(f"Join request is from socket which is already in the leader wait queue. Ignoring.")
            return
        self._player_queue.append((datetime.now(), ws, instruction_uuid))
        self._pending_room_management_responses[ws].put(
            RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, len(self._player_queue), Role.NONE), None, None))

    def join_follower_queue(self, ws, instruction_uuid=""):
        if ws in self._follower_queue:
            logger.info(f"Join request is from socket which is already in the follower wait queue. Ignoring.")
            return
        if ws in self._player_queue:
            logger.info(f"Join request is from follower socket which is already in the wait queue. Ignoring.")
            return
        if ws in self._leader_queue:
            logger.info(f"Join request is from socket which is already in the leader wait queue. Ignoring.")
            return
        self._follower_queue.append((datetime.now(), ws, instruction_uuid))
        self._pending_room_management_responses[ws].put(
            RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, len(self._follower_queue), Role.NONE), None, None))
    
    def join_leader_queue(self, ws, instruction_uuid=""):
        if ws in self._leader_queue:
            logger.info(f"Join request is from socket which is already in the leader wait queue. Ignoring.")
            return
        if ws in self._player_queue:
            logger.info(f"Join request is from leader socket which is already in the wait queue. Ignoring.")
            return
        if ws in self._follower_queue:
            logger.info(f"Join request is from leader socket which is already in the follow wait queue. Ignoring.")
            return
        self._leader_queue.append((datetime.now(), ws, instruction_uuid))
        self._pending_room_management_responses[ws].put(
            RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, len(self._leader_queue), Role.NONE), None, None))

    def handle_join_request(self, request, ws):
        logger.info(f"Received join request from : {str(ws)}. Queue size: {len(self._player_queue)}")
        worker = GetWorkerFromRemote(ws)
        if worker is None:
            logger.warning(f"Could not get worker from remote. Joining.")
            self.join_player_queue(ws, instruction_uuid=request.join_game_with_instruction_uuid)
            return
        if worker.qual_level in [WorkerQualLevel.EXPERT, WorkerQualLevel.LEADER]:
            self.join_player_queue(ws, instruction_uuid=request.join_game_with_instruction_uuid)
        elif worker.qual_level == WorkerQualLevel.FOLLOWER:
            self.join_follower_queue(ws, instruction_uuid=request.join_game_with_instruction_uuid)
        else:
            logger.warning(f"Worker has invalid qual level: {worker.qual_level}.")
            self._pending_room_management_responses[ws].put(
                RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, -1, Role.NONE, True), None, None))
            return
    
    def handle_follower_only_join_request(self, request, ws):
        logger.info(f"Received follower only join request from : {str(ws)}. Queue size: {len(self._follower_queue)}. uuid: {request.join_game_with_instruction_uuid}")
        self.join_follower_queue(ws, instruction_uuid=request.join_game_with_instruction_uuid)

    def handle_leader_only_join_request(self, request, ws):
        logger.info(f"Received leader only join request from : {str(ws)}. Queue size: {len(self._leader_queue)}")
        self.join_leader_queue(ws, instruction_uuid=request.join_game_with_instruction_uuid)

    def handle_leave_request(self, request, ws):
        if not ws in self._remotes:
            return RoomManagementResponse(RoomResponseType.ERROR, None, None, None, None, "You are not in a room.")
        room_id, player_id, _ = self._remotes[ws].as_tuple()
        self.disconnect_socket(ws)
        self._pending_room_management_responses[ws].put(
            RoomManagementResponse(RoomResponseType.LEAVE_NOTICE, None, None, LeaveRoomNotice("Player requested leave."), None))

    def handle_stats_request(self, request, ws):
        total_players = sum(
            [room.number_of_players() for room in self._rooms.values()])
        stats = StatsResponse(len(self._rooms), total_players, len(self._player_queue))
        self._pending_room_management_responses[ws].put(
            RoomManagementResponse(RoomResponseType.STATS, stats, None, None, None))
    
    def handle_map_sample_request(self, request, ws):
        self._pending_room_management_responses[ws].put(
            RoomManagementResponse(RoomResponseType.MAP_SAMPLE, None, None, None, CachedMapRetrieval().map()))

    def remove_socket_from_queue(self, ws):
        player_queue = deque()
        removed = False
        for ts, element, i_uuid in self._player_queue:
            if element == ws:
                logger.info("Removed socket from queue.")
                removed = True
                continue
            player_queue.append((ts, element, i_uuid))
        if not removed:
            logger.warning("Socket not found in queue!")
        self._player_queue = player_queue

        follower_queue = deque()
        removed = False
        for ts, element, i_uuid in self._follower_queue:
            if element == ws:
                logger.info("Removed socket from follower queue.")
                removed = True
                continue
            follower_queue.append((ts, element, i_uuid))
        if not removed:
            logger.warning("Socket not found in follower queue!")
        self._follower_queue = follower_queue

        leader_queue = deque()
        removed = False
        for ts, element, i_uuid in self._leader_queue:
            if element == ws:
                logger.info("Removed socket from leader queue.")
                removed = True
                continue
            leader_queue.append((ts, element, i_uuid))
        if not removed:
            logger.warning("Socket not found in leader queue!")
        self._leader_queue = leader_queue
    
    def handle_cancel_request(self, request, ws):
        # Iterate through the queue of followers and leaders,
        # removing the given socket.
        print("Received queue cancel request from : " + str(ws))
        self.remove_socket_from_queue(ws)
    
    def handle_request(self, request, ws):
        if request.type == message_to_server.MessageType.ROOM_MANAGEMENT:
            self.handle_room_request(request.room_request, ws)
        if request.type == message_to_server.MessageType.TUTORIAL_REQUEST:
            self.handle_tutorial_request(request.tutorial_request, ws)

    def handle_room_request(self, request, ws):
        if not ws in self._pending_room_management_responses:
            self._pending_room_management_responses[ws] = Queue()

        if request.type == RoomRequestType.JOIN:
            self.handle_join_request(request, ws)
        elif request.type == RoomRequestType.JOIN_FOLLOWER_ONLY:
            self.handle_follower_only_join_request(request, ws)
        elif request.type == RoomRequestType.JOIN_LEADER_ONLY:
            self.handle_leader_only_join_request(request, ws)
        elif request.type == RoomRequestType.LEAVE:
            self.handle_leave_request(request, ws)
        elif request.type == RoomRequestType.STATS:
            self.handle_stats_request(request, ws)
        elif request.type == RoomRequestType.CANCEL:
            self.handle_cancel_request(request, ws)
        elif request.type == RoomRequestType.MAP_SAMPLE:
            self.handle_map_sample_request(request, ws)
        else:
            logger.warn(f"Unknown request type: {request.type}")

    def drain_message(self, ws):
        if ws not in self._pending_room_management_responses:
            self._pending_room_management_responses[ws] = Queue()
        if not self._pending_room_management_responses[ws].empty():
            try:
                management_response = self._pending_room_management_responses[ws].get(False)
                logger.info(f"Drained Room Management message type {management_response.type} for {ws}.")
                logger.info(f"Remaining messages in queue: {self._pending_room_management_responses[ws].qsize()}")
                return message_from_server.RoomResponseFromServer(management_response)
            except queue.Empty:
                pass
        
        if ws not in self._pending_tutorial_messages:
            self._pending_tutorial_messages[ws] = Queue()
        if not self._pending_tutorial_messages[ws].empty():
            try:
                tutorial_response = self._pending_tutorial_messages[ws].get(False)
                logger.info(f"Drained tutorial response type {tutorial_response.type} for {ws}.")
                return message_from_server.TutorialResponseFromServer(tutorial_response)
            except queue.Empty:
                pass
        
        return None