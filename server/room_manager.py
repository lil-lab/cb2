""" Used to manage game rooms. """
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from messages.message_from_server import MessageFromServer
from messages.message_from_server import MessageType
from messages.rooms import Role
from messages.rooms import JoinResponse
from messages.rooms import LeaveRoomNotice
from messages.rooms import StatsResponse
from messages.rooms import RoomManagementRequest
from messages.rooms import RoomRequestType
from messages.rooms import RoomManagementResponse
from messages.rooms import RoomResponseType
from room import Room
from util import IdAssigner, SafePasswordCompare

import aiohttp
import asyncio
import datetime
import messages.rooms
import queue
import random


@dataclass_json()
@dataclass(frozen=True)
class SocketInfo:
    room_id: int
    player_id: int
    role: Role

    # Used to support selective destructuring of one or more keys.
    # e.g. room_id, player_id = socket_info["room_id", "player_id"]
    def __getitem__(self, keys):
        return iter(getattr(self, k) for k in keys)


class RoomManager(object):
    """ Used to manage game rooms. """

    def __init__(self):
        self._rooms = {}
        self._room_id_assigner = IdAssigner()
        self._remotes = {}  # {ws: SocketInfo}
        self._is_done = False
        self._follower_queue = queue.Queue()
        self._leader_queue = queue.Queue()

    async def disconnect_socket(self, ws):
        """ This socket terminated its connection. End the game that the person was in."""
        if not ws in self._remotes:
            return
        room_id, player_id = self._remotes[ws]["room_id", "player_id"]
        self._rooms[room_id].remote_player(player_id)
        # If a player leaves, the game ends for everyone in the room. Send them leave notices and end the game.
        self._rooms[room_id].stop()
        for socket in self._rooms[room_id].player_endpoints():
            if not socket.closed:
                leave_notice = LeaveRoomNotice(
                    "Other player disconnected, game ending.")
                msg = MessageFromServer(datetime.now(), MessageType.ROOM_MANAGEMENT_RESPONSE, None, None, None, RoomManagementResponse(
                    RoomResponseType.LEAVE_NOTICE, None, None, leave_notice))
                await socket.send_str(msg.to_json())
                socket.close()
        del self._remotes[ws]

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
            room.end()
        self._is_done = True

    def create_room(self):
        id = self._room_id_assigner.assign()
        self._rooms[id] = Room("Room #" + str(id), 2, id, None)
        self._rooms[id].start()
        return self._rooms[id]

    def cleanup_unused_rooms(self):
        for room in self._rooms.values():
            if room.is_empty():
                self.delete_room(room.id())

    def delete_room(self, id):
        self._rooms[id].end()
        del self._rooms[id]

    def available_room_id(self):
        for room_id in self._rooms.keys():
            if not self._rooms[room_id].is_full():
                return room_id
        return None

    async def matchmake(self):
        """ Runs asyncronously, creating rooms for pending followers and
        leaders. """
        while not self._is_done:
            await asyncio.sleep(1)
            leader, follower = self.get_leader_follower_match()
            if not leader or not follower:
                continue
            room = self.create_room()
            self._remotes[leader] = SocketInfo(
                room.id(), room.add_player(), Role.LEADER)
            self._remotes[follower] = SocketInfo(
                room.id(), room.add_player(), Role.FOLLOWER)

    def get_leader_follower_match(self):
        """ Returns a pair of leader, follower.

            Leaders and followers are removed from their respective queues. If
            either queue is empty, leaves the other untouched.
        """
        if self._leader_queue.empty() or self._follower_queue.empty():
            return None, None
        leader = self._leader_queue.get()
        follower = self._follower_queue.get()
        return leader, follower

    def handle_join_request(self, request, ws):
        # Assign a role depending on which role queue is smaller.
        if self._follower_queue.qsize() >= self._leader_queue.qsize():
            self._leader_queue.put(ws)
            return RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, self._leader_queue.qsize(), Role.NONE), None)
        else:
            self._follower_queue.put(ws)
            return RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(True, self._follower_queue.qsize(), Role.NONE), None)

    def handle_leave_request(self, request, ws):
        if not ws in self._remotes:
            return RoomManagementResponse(RoomResponseType.ERROR, "You are not in a room.")
        room_id, player_id = self._remotes[ws]["room_id", "player_id"]
        self._rooms[room_id].remote_player(player_id)
        del self._remotes[ws]
        return RoomManagementResponse(RoomResponseType.LEAVE_NOTICE, None, None, LeaveRoomNotice("Player requested leave."))

    def handle_stats_request(self, request, ws):
        total_players = sum(
            [room.number_of_players for room in self._rooms.values()])
        stats = StatsResponse(len(self._rooms), total_players,
                              self._follower_queue.qsize(), self._leader_queue.qsize())
        return RoomManagementResponse(RoomResponseType.STATS, stats, None, None)

    def handle_request(self, request, ws):
        if request.type == RoomRequestType.JOIN:
            return self.handle_join_request(request, ws)
        elif request.type == RoomRequestType.LEAVE:
            return self.handle_leave_request(request, ws)
        elif request.type == RoomRequestType.STATS:
            return self.handle_stats_request(request, ws)
        else:
            return RoomManagementResponse(RoomResponseType.ERROR, "Unknown request type.")
