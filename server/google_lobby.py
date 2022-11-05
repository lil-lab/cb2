""" A Lobby that's open to players signed in with Google SSO. """
import logging
from datetime import datetime, timedelta
from typing import Tuple

from aiohttp import web
from google.auth.transport import requests
from google.oauth2 import id_token

import server.lobby as lobby
from server.config.config import GlobalConfig
from server.lobby import LobbyType
from server.remote_table import GetRemote

logger = logging.getLogger(__name__)

TESTING_CLIENT_ID = (
    "787231947800-ee2g4lptmfa0av2qb26n1qu60hf5j2fd.apps.googleusercontent.com"
)


class GoogleLobby(lobby.Lobby):
    """Used to manage Google account authenticated rooms."""

    def __init__(self, lobby_name):
        # Call the superconstructor.
        super().__init__(lobby_name=lobby_name)

    # OVERRIDES Lobby.accept_player()
    def accept_player(self, ws: web.WebSocketResponse) -> bool:
        config = GlobalConfig()
        remote = GetRemote(ws)
        if remote.google_auth_token is None:
            return False
        try:
            idinfo = id_token.verify_oauth2_token(
                remote.google_auth_token,
                requests.Request(),
                config.google_oauth_client_id,
            )
            if idinfo["iss"] not in [
                "accounts.google.com",
                "https://accounts.google.com",
            ]:
                raise ValueError("Wrong issuer.")
            # ID token is valid. Get the user's Google Account ID from the decoded token.
            remote.google_user_id = idinfo["sub"]
            return True
        except ValueError:
            # Invalid token
            return False

    # OVERRIDES Lobby.lobby_type()
    def lobby_type(self) -> LobbyType:
        return LobbyType.GOOGLE

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
        if datetime.now() - ts > timedelta(seconds=1):
            (_, player1, i_uuid_1) = self._player_queue.popleft()
            (_, player2, i_uuid_2) = self._player_queue.popleft()
            # This is the main difference between this class and mturk lobby. If
            # two general players are matched, first one is given leader (rather
            # than choosing based on experience).
            leader, follower = (player1, player2)
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
