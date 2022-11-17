""" A Lobby for mturk players. """
import logging
from datetime import datetime, timedelta
from typing import Tuple

from aiohttp import web

import server.lobby as lobby
from server.lobby import LobbyType
from server.messages.rooms import (
    JoinResponse,
    Role,
    RoomManagementRequest,
    RoomManagementResponse,
    RoomResponseType,
)
from server.mturk_experience import GetWorkerExperienceEntry
from server.remote_table import GetWorkerFromRemote
from server.schemas.mturk import WorkerQualLevel

logger = logging.getLogger(__name__)


class MturkLobby(lobby.Lobby):
    """Used to manage game rooms."""

    def __init__(self, lobby_name):
        # Call the superconstructor.
        super().__init__(lobby_name=lobby_name)

    def is_mturk_player(self, ws: web.WebSocketResponse) -> bool:
        return GetWorkerFromRemote(ws) is not None

    def accept_player(self, ws: web.WebSocketResponse) -> bool:
        return self.is_mturk_player(ws)

    # OVERRIDES Lobby.get_leader_follower_match().
    def get_leader_follower_match(
        self,
    ) -> Tuple[web.WebSocketResponse, web.WebSocketResponse, str]:
        """Returns a tuple of (leader, follower, instruction_uuid) if there is a match, otherwise returns None.

        If neither client requested to play a game from a specific UUID,
        then UUID will be empty string.

        There are three queues of players: General players, follower-only,
        and leader-only players.
        General players must wait for either a follower or for 10 seconds to
        pass. Once 10 seconds have passed, they can match with other general
        players.
        Follower-only players must wait for a general player to become
        available. If a follower has waited for > 5m, they're expired from
        the queue.
        There's also a leader-only queue, which is similar to follower-only.

        If multiple matches are available, selects the most-experienced
        leader and least-experienced follower.

        Leaders and followers are removed from their respective queues. If
        either queue is empty, leaves the other untouched.
        """
        # First of all, if the first follower has been waiting for 5m, remove them from the queue.
        if len(self._follower_queue) > 0:
            (ts, follower, i_uuid) = self._follower_queue[0]
            if datetime.now() - ts > timedelta(minutes=5):
                self._follower_queue.popleft()
                # Queue a room management response to notify the follower that they've been removed from the queue.
                self._pending_room_management_responses[follower].put(
                    RoomManagementResponse(
                        RoomResponseType.JOIN_RESPONSE,
                        None,
                        JoinResponse(False, -1, Role.NONE, True),
                        None,
                        None,
                    )
                )

        # If a general player has been waiting alone for 5m, remove them from the queue.
        if len(self._player_queue) > 0:
            (ts, player, i_uuid) = self._player_queue[0]
            if datetime.now() - ts > timedelta(minutes=5):
                self._player_queue.popleft()
                # Queue a room management response to notify the player that they've been removed from the queue.
                self._pending_room_management_responses[player].put(
                    RoomManagementResponse(
                        RoomResponseType.JOIN_RESPONSE,
                        None,
                        JoinResponse(False, -1, Role.NONE, True),
                        None,
                        None,
                    )
                )

        # If a leader has been waiting alone for 5m, remove them from the queue.
        if len(self._leader_queue) > 0:
            (ts, leader, i_uuid) = self._leader_queue[0]
            if datetime.now() - ts > timedelta(minutes=5):
                self._leader_queue.popleft()
                # Queue a room management response to notify the leader that they've been removed from the queue.
                self._pending_room_management_responses[leader].put(
                    RoomManagementResponse(
                        RoomResponseType.JOIN_RESPONSE,
                        None,
                        JoinResponse(False, -1, Role.NONE, True),
                        None,
                        None,
                    )
                )

        # If there's a leader in the leader queue and a follower in the follower queue, match them.
        if len(self._leader_queue) > 0 and len(self._follower_queue) > 0:
            (_, leader, l_i_uuid) = self._leader_queue.popleft()
            (_, follower, f_i_uuid) = self._follower_queue.popleft()
            if l_i_uuid:
                i_uuid = l_i_uuid
            elif f_i_uuid:
                i_uuid = f_i_uuid
            else:
                i_uuid = ""
            return leader, follower, i_uuid

        # If there's no general players, a match can't be made.
        if len(self._player_queue) < 1:
            return None, None, ""

        # If there's a leader and a general player, match them.
        if len(self._leader_queue) > 0 and len(self._player_queue) > 0:
            (_, leader, l_i_uuid) = self._leader_queue.popleft()
            (_, player, f_i_uuid) = self._player_queue.popleft()
            if l_i_uuid:
                i_uuid = l_i_uuid
            elif f_i_uuid:
                i_uuid = f_i_uuid
            else:
                i_uuid = ""
            return leader, player, i_uuid

        # If there's a follower waiting, match them with the first general player.
        if len(self._follower_queue) >= 1:
            (_, leader, l_i_uuid) = self._player_queue.popleft()
            (_, follower, f_i_uuid) = self._follower_queue.popleft()
            if l_i_uuid:
                i_uuid = l_i_uuid
            elif f_i_uuid:
                i_uuid = f_i_uuid
            else:
                i_uuid = ""
            return leader, follower, i_uuid

        # If there's no follower waiting, check if there's two general players...
        if len(self._player_queue) < 2:
            return (None, None, "")

        # If a general player has been waiting for >= 10 seconds with no follower, match them with another general player.
        (ts, _, _) = self._player_queue[0]
        if datetime.now() - ts > timedelta(seconds=10):
            (_, player1, i_uuid_1) = self._player_queue.popleft()
            (_, player2, i_uuid_2) = self._player_queue.popleft()
            leader, follower = self.assign_leader_follower(player1, player2)
            if i_uuid_1:
                i_uuid = i_uuid_1
            elif i_uuid_2:
                i_uuid = i_uuid_2
            else:
                i_uuid = ""
            if leader is None or follower is None:
                logger.warning(
                    "Could not assign leader and follower based on experience. Using random assignment."
                )
                return (player1, player2, i_uuid)
            return leader, follower, i_uuid
        return None, None

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
            logger.warning(f"Could not get mturk worker from remote. Joining.")
            self.boot_from_queue(ws)
            return
        worker = GetWorkerFromRemote(ws)
        if worker is None:
            self.boot_from_queue(ws)
            return
        if worker.qual_level in [WorkerQualLevel.EXPERT, WorkerQualLevel.LEADER]:
            self.join_player_queue(ws, request)
        elif worker.qual_level == WorkerQualLevel.FOLLOWER:
            self.join_follower_queue(ws, request)
        else:
            logger.warning(f"Worker has invalid qual level: {worker.qual_level}.")
            self.boot_from_queue(ws)
            return

    # OVERRIDES Lobby.lobby_type()
    def lobby_type(self) -> LobbyType:
        return LobbyType.MTURK

    def assign_leader_follower(
        self, player1: web.WebSocketResponse, player2: web.WebSocketResponse
    ):
        """Given two websockets attached to mturk players, assigns roles to
        each based on experience. Returns (leader, follower) or (None, None) if
        missing data on either player.
        """
        worker1 = GetWorkerFromRemote(player1)
        worker2 = GetWorkerFromRemote(player2)
        if worker1 is None and worker2 is None:
            return None, None
        elif worker1 is None:
            return player2, player1
        elif worker2 is None:
            return player1, player2
        exp1 = GetWorkerExperienceEntry(worker1.hashed_id)
        exp2 = GetWorkerExperienceEntry(worker2.hashed_id)
        # For each exp entry, calculate the average score of the last 5 lead games from last_1k_lead_scores and use that to determine the leader.
        if exp1 is None or exp2 is None:
            return None, None
        if exp1.last_1k_lead_scores is None or exp2.last_1k_lead_scores is None:
            logger.info(f"No data to determine either player.")
            return None, None
        # We have enough data on both players!
        exp1_lead_games = min(len(exp1.last_1k_lead_scores), 10)
        leader1_score = (
            sum(exp1.last_1k_lead_scores[-10:]) / exp1_lead_games
            if exp1_lead_games > 0
            else 0
        )
        exp2_lead_games = min(len(exp2.last_1k_lead_scores), 10)
        leader2_score = (
            sum(exp2.last_1k_lead_scores[-10:]) / exp2_lead_games
            if exp2_lead_games > 0
            else 0
        )
        if leader1_score > leader2_score:
            return player1, player2
        elif leader1_score < leader2_score:
            return player2, player1
        else:
            return player1, player2
