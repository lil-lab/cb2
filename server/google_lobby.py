""" A Lobby that's open to players signed in with Google SSO. """
import logging
from datetime import datetime, timedelta
from typing import Tuple

from aiohttp import web

import server.lobby as lobby
from server.lobby import LobbyType
from server.messages.rooms import RoomManagementRequest
from server.remote_table import GetRemote

logger = logging.getLogger(__name__)

TESTING_CLIENT_ID = (
    "787231947800-ee2g4lptmfa0av2qb26n1qu60hf5j2fd.apps.googleusercontent.com"
)


class GoogleLobby(lobby.Lobby):
    """Used to manage Google account authenticated rooms."""

    def __init__(self, lobby_name, lobby_comment):
        # Call the superconstructor.
        super().__init__(lobby_name=lobby_name, lobby_comment=lobby_comment)

    def accept_player(self, ws: web.WebSocketResponse) -> bool:
        remote = GetRemote(ws)
        if remote is None:
            return False
        if remote.google_id is None:
            return False
        return True

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

        # If there's a leader in the leader queue and a follower in the follower queue, match them.
        if len(self._leader_queue) > 0 and len(self._follower_queue) > 0:
            (_, leader, l_e_uuid) = self._leader_queue.popleft()
            (_, follower, f_e_uuid) = self._follower_queue.popleft()
            if l_e_uuid:
                e_uuid = l_e_uuid
            elif f_e_uuid:
                e_uuid = f_e_uuid
            else:
                e_uuid = ""
            return leader, follower, e_uuid

        # If there's no general players, a match can't be made.
        if len(self._player_queue) < 1:
            return None, None, ""

        # If there's a leader and a general player, match them.
        if len(self._leader_queue) > 0 and len(self._player_queue) > 0:
            (_, leader, l_e_uuid) = self._leader_queue.popleft()
            (_, player, f_e_uuid) = self._player_queue.popleft()
            if l_e_uuid:
                e_uuid = l_e_uuid
            elif f_e_uuid:
                e_uuid = f_e_uuid
            else:
                e_uuid = ""
            return leader, player, e_uuid

        # If there's a follower waiting, match them with the first general player.
        if len(self._follower_queue) >= 1:
            (_, leader, l_e_uuid) = self._player_queue.popleft()
            (_, follower, f_e_uuid) = self._follower_queue.popleft()
            if l_e_uuid:
                e_uuid = l_e_uuid
            elif f_e_uuid:
                e_uuid = f_e_uuid
            else:
                e_uuid = ""
            return leader, follower, e_uuid

        # If there's no follower waiting, check if there's two general players...
        if len(self._player_queue) < 2:
            return (None, None, "")

        # If a general player has been waiting for >= 10 seconds with no follower, match them with another general player.
        (ts, _, _) = self._player_queue[0]
        if datetime.now() - ts > timedelta(seconds=1):
            (_, player1, e_uuid_1) = self._player_queue.popleft()
            (_, player2, e_uuid_2) = self._player_queue.popleft()
            # This is the main difference between this class and mturk lobby. If
            # two general players are matched, first one is given leader (rather
            # than choosing based on experience).
            leader, follower = (player1, player2)
            if e_uuid_1:
                e_uuid = e_uuid_1
            elif e_uuid_2:
                e_uuid = e_uuid_2
            else:
                e_uuid = ""
            if leader is None or follower is None:
                logger.warning(
                    "Could not assign leader and follower based on experience. Using random assignment."
                )
                return (player1, player2, e_uuid)
            return leader, follower, e_uuid
        return None, None

    # OVERRIDES Lobby.handle_join_request().
    def handle_join_request(
        self, request: RoomManagementRequest, ws: web.WebSocketResponse
    ) -> None:
        if not self.accept_player(ws):
            logger.info(f"Rejected player {ws} due to invalid Google auth token.")
            self.boot_from_queue(ws)
            return
        # For now, toss all players in the player queue. Later we'll add Google
        # exp tracking and do something fancier.
        self.join_player_queue(ws, request)

    # OVERRIDES Lobby.lobby_type()
    def lobby_type(self) -> LobbyType:
        return LobbyType.GOOGLE

    # Overrides Lobby.handle_replay_request()
    def handle_replay_request(
        self, request: RoomManagementRequest, ws: web.WebSocketResponse
    ) -> None:
        """Handles a request to join a replay room. In most lobbies, this should be ignored (except lobbies supporting replay)."""
        logger.warning(
            f"Received replay request from {str(ws)} in non-replay lobby. Ignoring."
        )
        self.boot_from_queue(ws)
        return
