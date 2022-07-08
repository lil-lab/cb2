""" Used to manage game rooms. """
from collections import deque
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime, timedelta
from map_provider import CachedMapRetrieval
from messages import message_from_server
from messages import message_to_server
from messages.logs import GameInfo
from messages.rooms import Role
from messages.rooms import JoinResponse
from messages.rooms import LeaveRoomNotice
from messages.rooms import StatsResponse
from messages.rooms import RoomManagementRequest
from messages.rooms import RoomRequestType
from messages.rooms import RoomManagementResponse
from messages.rooms import RoomResponseType
from messages.tutorials import RoleFromTutorialName, TutorialRequestType, TutorialResponse, TutorialResponseType
from queue import Queue
from remote_table import GetRemote 
from room import Room, RoomType
from util import IdAssigner, GetCommitHash

import aiohttp
import asyncio
import logging
import messages.rooms
import pathlib
import random
import schemas.game

logger = logging.getLogger()

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


class RoomManager(object):
    """ Used to manage game rooms. """

    def __init__(self):
        self._rooms = {}
        self._room_id_assigner = IdAssigner()
        self._remotes = {}  # {ws: SocketInfo}
        self._is_done = False
        self._player_queue = deque()
        self._follower_queue = deque()
        self._base_log_directory = pathlib.Path("/dev/null")
        self._pending_room_management_responses = {}  # {ws: room_management_response}
        self._pending_tutorial_messages = {}  # {ws: tutorial_response}
    
    def register_game_logging_directory(self, dir):
        self._base_log_directory = dir
    
    def player_queue(self):
        return self._player_queue
    
    def follower_queue(self):
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

    def create_room(self, id, game_record: schemas.game.Game,
                    type: RoomType = RoomType.GAME, tutorial_name: str = ""):
        self._rooms[id] = Room(
            # Room name.
            "Room #" + str(id) + ("(TUTORIAL)" if type == RoomType.TUTORIAL else ""),
            # Max number of players.
            2,
            # Room ID.
            id,
            game_record,
            type,
            tutorial_name)
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
            await asyncio.sleep(0)
            self.delete_unused_rooms()
    
    def create_tutorial(self, player, tutorial_name):
        logger.info(f"Creating tutorial room for {player}.")

        # Setup room log directory.
        game_record = schemas.game.Game()
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
        print("Creating new tutorial room " + room.name())
        role = RoleFromTutorialName(tutorial_name)
        player_id = room.add_player(player, role)
        self._remotes[player] = SocketInfo(room.id(), player_id, role)

        player_remote = GetRemote(player)

        game_info_path = pathlib.Path(log_directory, "game_info.jsonl.log")
        game_info_log = game_info_path.open("w")
        print(player_remote)
        game_info = GameInfo(datetime.now(), game_id, game_name, [role], [player_id])
        game_info_log.write(game_info.to_json() + "\n")
        game_info_log.close()
        return room

    async def matchmake(self):
        """ Runs asyncronously, creating rooms for pending followers and
        leaders. """
        while not self._is_done:
            await asyncio.sleep(0)
            leader, follower = self.get_leader_follower_match()

            if (leader is None) or (follower is None):
                continue

            logger.info(f"Creating room for {leader} and {follower}. Queue size: {len(self._player_queue)} Follower Queue: {len(self._follower_queue)}")

            # Setup room log directory.
            game_record = schemas.game.Game()
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
            print("Creating new game " + room.name())
            leader_id = room.add_player(leader, Role.LEADER)
            follower_id = room.add_player(follower, Role.FOLLOWER)
            self._remotes[leader] = SocketInfo(room.id(), leader_id, Role.LEADER)
            self._remotes[follower] = SocketInfo(room.id(), follower_id, Role.FOLLOWER)

            leader_remote = GetRemote(leader)
            follower_remote = GetRemote(follower)

            game_info_path = pathlib.Path(log_directory, "game_info.jsonl.log")
            game_info_log = game_info_path.open("w")
            game_info = GameInfo(datetime.now(), game_id, game_name, [Role.LEADER, Role.FOLLOWER], [leader_id, follower_id])
            game_info_log.write(game_info.to_json() + "\n")
            game_info_log.close()

            self._pending_room_management_responses[leader].put(
                RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(True, 0, Role.LEADER), None, None))
            self._pending_room_management_responses[follower].put(
                RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(True, 0, Role.FOLLOWER), None, None))

    def get_leader_follower_match(self):
        """ Returns a pair of leader, follower.

            There are two queues of players: General players and follower-only
            players. General players must wait for either a follower or for 10
            seconds to pass. Once 10 seconds have passed, they can match with
            other general players. 
            Follower-only players must wait for a general player to become
            available. If a follower has waited for > 5m, they're expired from
            the queue.
            
            Leaders and followers are removed from their respective queues. If
            either queue is empty, leaves the other untouched.
        """
        # First of all, if the player queue is empty and the first follower has been waiting for 5m, remove them from the queue.
        if len(self._player_queue) == 0 and len(self._follower_queue) > 0:
            (ts, follower) = self._follower_queue[0]
            if datetime.now() - ts > timedelta(minutes=5):
                self._follower_queue.popleft()
                # Queue a room management response to notify the follower that they've been removed from the queue.
                self._pending_room_management_responses[follower].put(
                    RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, -1, Role.NONE, True), None, None,))

        # If there's no general players, a match can't be made.
        if len(self._player_queue) < 1:
            return None, None
        
        # If there's a follower waiting, match them with the first general player.
        if len(self._follower_queue) > 1:
            (_, leader) = self._player_queue.popleft()
            (_, follower) = self._follower_queue.popleft()
            return leader, follower

        # If there's no follower waiting, check if there's two general players...
        if len(self._player_queue) < 2:
            return

        # If a general player has been waiting for >= 10 seconds with no follower, match them with another general player.
        (ts, _) = self._player_queue[0] 
        if datetime.now() - ts > timedelta(seconds=10):
            (_, leader) = self._player_queue.popleft()
            (_, follower) = self._player_queue.popleft()
            return leader, follower
        
        # If a general player has been waiting alone for 5m, remove them from the queue.
        (ts, player) = self._player_queue[0]
        if datetime.now() - ts > timedelta(minutes=5):
            self._player_queue.popleft()
            # Queue a room management response to notify the player that they've been removed from the queue.
            self._pending_room_management_responses[player].put(
                RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, -1, Role.NONE, True), None, None))
        
        return None, None
    
    def handle_tutorial_request(self, tutorial_request, ws):
        if ws not in self._pending_tutorial_messages:
            self._pending_tutorial_messages[ws] = Queue()
        if tutorial_request.type == TutorialRequestType.START_TUTORIAL:
            room = self.create_tutorial(ws, tutorial_request.tutorial_name)
            self._pending_tutorial_messages[ws].put(
                TutorialResponse(TutorialResponseType.STARTED, tutorial_request.tutorial_name, None, None))
        else:
            logger.warning(f'Room manager received incorrect tutorial request type {tutorial_request.type}.')

    def handle_join_request(self, request, ws):
        # Assign a role depending on which role queue is smaller.
        logger.info(f"Received join request from : {str(ws)}. Queue size: {len(self._player_queue)}")
        if ws in self._player_queue:
            logger.info(f"Join request is from socket which is already in the wait queue. Ignoring.")
            return
        self._player_queue.append((datetime.now(), ws))
        self._pending_room_management_responses[ws].put(
            RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, len(self._player_queue), Role.NONE), None, None))
    
    def handle_follower_only_join_request(self, request, ws):
        logger.info(f"Received follower only join request from : {str(ws)}. Queue size: {len(self._follower_queue)}")
        if ws in self._follower_queue:
            logger.info(f"Join request is from socket which is already in the follower wait queue. Ignoring.")
            return
        if ws in self._player_queue:
            logger.info(f"Join request is from follower socket which is already in the wait queue. Ignoring.")
            return
        
        self._follower_queue.append((datetime.now(), ws))
        self._pending_room_management_responses[ws].put(
            RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, len(self._follower_queue), Role.NONE), None, None))

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
        for ts, element in self._player_queue:
            if element == ws:
                logger.info("Removed socket from queue.")
                removed = True
                continue
            logger.info(f"{element}(element) != {ws}(ws -- to be deleted)")
            player_queue.append((ts, element))
        if not removed:
            logger.warning("Socket not found in queue!")
        self._player_queue = player_queue

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
        elif request.type == RoomRequestType.FOLLOWER_ONLY_JOIN:
            self.handle_follower_only_join_request(request, ws)
        elif request.type == RoomRequestType.LEAVE:
            self.handle_leave_request(request, ws)
        elif request.type == RoomRequestType.STATS:
            self.handle_stats_request(request, ws)
        elif request.type == RoomRequestType.CANCEL:
            self.handle_cancel_request(request, ws)
        elif request.type == RoomRequestType.MAP_SAMPLE:
            self.handle_map_sample_request(request, ws)
        else:
            logger.WARN("Unknown request type.")

    def drain_message(self, ws):
        if ws not in self._pending_room_management_responses:
            self._pending_room_management_responses[ws] = Queue()
        if not self._pending_room_management_responses[ws].empty():
            management_response = self._pending_room_management_responses[ws].get()
            logger.info(f"Drained Room Management message type {management_response.type} for {ws}.")
            return message_from_server.RoomResponseFromServer(management_response)
        
        if ws not in self._pending_tutorial_messages:
            self._pending_tutorial_messages[ws] = Queue()
        if not self._pending_tutorial_messages[ws].empty():
            tutorial_response = self._pending_tutorial_messages[ws].get()
            logger.info(f"Drained tutorial response type {tutorial_response.type} for {ws}.")
            return message_from_server.TutorialResponseFromServer(tutorial_response)
        
        return None