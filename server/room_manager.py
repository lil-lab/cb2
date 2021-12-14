""" Used to manage game rooms. """
from dataclasses import dataclass, field, astuple
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from messages import message_from_server
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
import logging
import messages.rooms
import queue
import random

logger = logging.getLogger()

@dataclass_json()
@dataclass(frozen=True)
class SocketInfo:
    room_id: int
    player_id: int
    role: Role


class RoomManager(object):
    """ Used to manage game rooms. """

    def __init__(self):
        self._rooms = {}
        self._room_id_assigner = IdAssigner()
        self._remotes = {}  # {ws: SocketInfo}
        self._is_done = False
        self._player_queue = queue.Queue()

    async def disconnect_socket(self, ws):
        """ This socket terminated its connection. End the game that the person was in."""
        self.remove_socket_from_queue(ws)
        if not ws in self._remotes:
            logging.info("Socket not found in self._remotes!")
            return
        room_id, player_id, _ = astuple(self._remotes[ws])
        if not room_id in self._rooms:
            # The room was already terminated by the other player.
            del self._remotes[ws]
            return
        self._rooms[room_id].remove_player(player_id, ws)
        # If a player leaves, the game ends for everyone in the room. Send them leave notices and end the game.
        self._rooms[room_id].stop()
        for socket in self._rooms[room_id].player_endpoints():
            if not socket.closed:
                leave_notice = LeaveRoomNotice(
                    "Other player disconnected, game ending.")
                msg = message_from_server.RoomResponseFromServer(RoomManagementResponse(
                    RoomResponseType.LEAVE_NOTICE, None, None, leave_notice))
                await socket.send_str(msg.to_json())
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

    def create_room(self):
        id = self._room_id_assigner.alloc()
        self._rooms[id] = Room("Room #" + str(id), 2, id, None)
        self._rooms[id].start()
        return self._rooms[id]

    def delete_unused_rooms(self):
        for room in self._rooms.values():
            if room.is_empty():
                logger.info(f"Deleting unused room: {room.name()}")
                self.delete_room(room.id())

    def delete_room(self, id):
        self._rooms[id].stop()
        del self._rooms[id]

    def available_room_id(self):
        for room_id in self._rooms.keys():
            if not self._rooms[room_id].is_full():
                return room_id
        return None
    
    async def cleanup_rooms(self):
        while not self._is_done:
            await asyncio.sleep(0.001)
            self.delete_unused_rooms()

    async def matchmake(self):
        """ Runs asyncronously, creating rooms for pending followers and
        leaders. """
        while not self._is_done:
            await asyncio.sleep(0.001)
            leader, follower = self.get_leader_follower_match()
            if (leader is None) or (follower is None):
                continue
            room = self.create_room()
            print("Creating new game " + room.name())
            self._remotes[leader] = SocketInfo(
                room.id(), room.add_player(leader, Role.LEADER), Role.LEADER)
            self._remotes[follower] = SocketInfo(
                room.id(), room.add_player(follower, Role.FOLLOWER), Role.FOLLOWER)

    def get_leader_follower_match(self):
        """ Returns a pair of leader, follower.

            Leaders and followers are removed from their respective queues. If
            either queue is empty, leaves the other untouched.
        """
        if self._player_queue.qsize() < 2:
            return None, None
        leader = self._player_queue.get()
        follower = self._player_queue.get()
        return leader, follower

    async def handle_join_request(self, request, ws):
        # Assign a role depending on which role queue is smaller.
        print("Received join request from : " + str(ws))
        self._player_queue.put(ws)
        return RoomManagementResponse(RoomResponseType.JOIN_RESPONSE, None, JoinResponse(False, self._player_queue.qsize(), Role.NONE), None)

    async def handle_leave_request(self, request, ws):
        if not ws in self._remotes:
            return RoomManagementResponse(RoomResponseType.ERROR, None, None, None, "You are not in a room.")
        room_id, player_id, _ = astuple(self._remotes[ws])
        await self.disconnect_socket(ws)
        return RoomManagementResponse(RoomResponseType.LEAVE_NOTICE, None, None, LeaveRoomNotice("Player requested leave."))

    async def handle_stats_request(self, request, ws):
        total_players = sum(
            [room.number_of_players() for room in self._rooms.values()])
        stats = StatsResponse(len(self._rooms), total_players, self._player_queue.qsize())
        return RoomManagementResponse(RoomResponseType.STATS, stats, None, None)

    def remove_socket_from_queue(self, ws):
        player_queue = queue.Queue()
        while not self._player_queue.empty():
            player = self._player_queue.get()
            if player != ws:
                player_queue.put(player)
        self._player_queue = player_queue

    async def handle_cancel_request(self, request, ws):
        # Iterate through the queue of followers and leaders,
        # removing the given socket.
        print("Client requested cancellation")
        self.remove_socket_from_queue(ws)

    async def handle_request(self, request, ws):
        if request.type == RoomRequestType.JOIN:
            return await self.handle_join_request(request, ws)
        elif request.type == RoomRequestType.LEAVE:
            return await self.handle_leave_request(request, ws)
        elif request.type == RoomRequestType.STATS:
            return await self.handle_stats_request(request, ws)
        elif request.type == RoomRequestType.CANCEL:
            return await self.handle_cancel_request(request, ws)
        else:
            return RoomManagementResponse(RoomResponseType.ERROR, "Unknown request type.")
