""" A Lobby for mturk players. """
import logging
from datetime import datetime, timedelta
from typing import Tuple

from aiohttp import web

import server.lobby as lobby
from server.lobby import LobbyType
from server.messages.rooms import RoomManagementRequest
from server.messages.user_info import UserType
from server.remote_table import GetRemote, GetWorkerFromRemote
from server.schemas.mturk import WorkerQualLevel

logger = logging.getLogger(__name__)


class FollowerPilotLobby(lobby.Lobby):
    """Used to manage game rooms."""

    def __init__(self, lobby_info):
        # Call the superconstructor.
        super().__init__(lobby_info)

    def is_mturk_player(self, ws: web.WebSocketResponse) -> bool:
        return GetWorkerFromRemote(ws) is not None

    def is_bot(self, ws: web.WebSocketResponse) -> bool:
        remote = GetRemote(ws)
        return remote is not None and remote.user_type == UserType.BOT

    def accept_player(self, ws: web.WebSocketResponse) -> bool:
        return self.is_mturk_player(ws) or self.is_bot(ws)

    # OVERRIDES Lobby.get_leader_follower_match().
    def get_leader_follower_match(
        self,
    ) -> Tuple[web.WebSocketResponse, web.WebSocketResponse, str]:
        """Returns a tuple of (leader, follower, instruction_uuid) if there is a match, otherwise returns None.

        If neither client requested to play a game from a specific UUID,
        then UUID will be empty string.

        There are three queues of players: General players, follower-only,
        and leader-only players. This lobby only uses the follower-only and
        leader-only queues.

        Follower-only queues can contain either human MTurk workers or follower
        bots, while leader-only queues only contain human MTurk workers. If a worker
        is qualified to be a leader, they will always be sent to the leader-only queue.

        Leader-only players are preferentially matched with human followers. If 10 seconds
        pass and there are no humans in the follower queue, the leader will be matched
        with the first player in the follower queue. If a queued player gets no matches
        in 5 minutes, they are removed from the queue.

        Leaders and followers are removed from their respective queues. If
        either queue is empty, leaves the other untouched.
        """
        # First of all, if the first follower has been waiting for 5m, remove them from the queue.
        if len(self._follower_queue) > 0:
            (ts, follower, e_uuid) = self._follower_queue[0]
            if datetime.now() - ts > timedelta(minutes=5):
                self._follower_queue.popleft()
                # Queue a room management response to notify the follower that they've been removed from the queue.
                self.boot_from_queue(follower)

        # If a general player has been waiting alone for 5m, remove them from the queue.
        if len(self._player_queue) > 0:
            (ts, player, e_uuid) = self._player_queue[0]
            if datetime.now() - ts > timedelta(minutes=5):
                self._player_queue.popleft()
                # Queue a room management response to notify the player that they've been removed from the queue.
                self.boot_from_queue(player)

        # If a leader has been waiting alone for 5m, remove them from the queue.
        if len(self._leader_queue) > 0:
            (ts, leader, e_uuid) = self._leader_queue[0]
            if datetime.now() - ts > timedelta(minutes=5):
                self._leader_queue.popleft()
                # Queue a room management response to notify the leader that they've been removed from the queue.
                self.boot_from_queue(leader)

        # If there's a leader in the leader queue and a follower in follower queue:
        if len(self._leader_queue) > 0 and len(self._follower_queue) > 0:
            (ts_l, leader, l_e_uuid) = self._leader_queue[0]

            if datetime.now() - ts_l < timedelta(seconds=10):
                # 1: In first 10 seconds, only match with human players
                human_follower = self._pop_human_follower()
                if human_follower is not None:
                    (_, leader, l_e_uuid) = self._leader_queue.popleft()
                    (_, follower, f_e_uuid) = human_follower
                    if l_e_uuid:
                        e_uuid = l_e_uuid
                    elif f_e_uuid:
                        e_uuid = f_e_uuid
                    else:
                        e_uuid = ""
                    return leader, follower, e_uuid
            else:
                # 2: No humans in the first 10 seconds. Match with the first follower in the queue.
                (_, leader, l_e_uuid) = self._leader_queue.popleft()
                (_, follower, f_e_uuid) = self._follower_queue.popleft()
                if l_e_uuid:
                    e_uuid = l_e_uuid
                elif f_e_uuid:
                    e_uuid = f_e_uuid
                else:
                    e_uuid = ""
                return leader, follower, e_uuid

        # For these experiments, assume that players are only assigned leader/follower only roles
        return None, None, ""

    # OVERRIDES Lobby.handle_join_request()
    def handle_join_request(
        self, request: RoomManagementRequest, ws: web.WebSocketResponse
    ) -> None:
        """Handles a join request from a player.

        You should use the following functions to put the player in a queue:
        self.join_player_queue(ws, request)
        self.join_follower_queue(ws, request)
        self.join_leader_queue(ws, request)

        If the player isn't valid, reject them by calling:
        self.boot_from_queue(ws)
        """
        logger.info(
            f"Received join request from : {str(ws)}. Queue size: {len(self._player_queue)}"
        )
        if not self.accept_player(ws):
            logger.warning(f"Could not get mturk worker or bot from remote. Joining.")
            self.boot_from_queue(ws)
            return

        # If the remote is for a bot, add to follower queue
        if self.is_bot(ws):
            self.join_follower_queue(ws, request)
            return

        # Add AMT workers to queue: Restrict to leader and follower only
        worker = GetWorkerFromRemote(ws)
        if worker is None:
            self.boot_from_queue(ws)
            return
        if worker.qual_level in [WorkerQualLevel.EXPERT, WorkerQualLevel.LEADER]:
            self.join_leader_queue(ws, request)
        elif worker.qual_level == WorkerQualLevel.FOLLOWER:
            self.join_follower_queue(ws, request)
        else:
            logger.warning(f"Worker has invalid qual level: {worker.qual_level}.")
            self.boot_from_queue(ws)
            return

    # OVERRIDES Lobby.lobby_type()
    def lobby_type(self) -> LobbyType:
        return LobbyType.FOLLOWER_PILOT

    def _pop_human_follower(self):
        """
        This will be hacky, but given that there won't be that many
        AMT workers in this lobby, I'd say it's ok.
        """
        human_follower = None

        # Pop all items until you reach a human follower
        popped = []
        while len(self._follower_queue) > 0:
            curr_follower = self._follower_queue.popleft()
            if self.is_mturk_player(curr_follower[1]):
                human_follower = curr_follower
                break
            popped.append(curr_follower)

        # Add all popped items before the human follower back
        for i in range(len(popped) - 1, -1, -1):
            curr_follower = popped[i]
            self._follower_queue.appendleft(curr_follower)

        return human_follower

    # Overrides Lobby.handle_replay_request()
    def handle_replay_request(
        self, request: RoomManagementRequest, ws: web.WebSocketResponse
    ) -> None:
        """Handles a request to join a replay room. In most lobbies, this should be ignored (except lobbies supporting replay)."""
        logger.warning(
            f"Received replay request from {str(ws)} in non-replay lobby. Ignoring."
        )
        self.boot_from_queue(ws)
