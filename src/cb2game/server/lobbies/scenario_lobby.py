""" A Lobby that's used for FMRI scenarios. """
import logging
from typing import Tuple

from aiohttp import web

import cb2game.server.lobby as lobby
from cb2game.server.lobby import LobbyType
from cb2game.server.messages.replay_messages import ReplayRequest
from cb2game.server.messages.rooms import RoomManagementRequest

logger = logging.getLogger(__name__)


class ScenarioLobby(lobby.Lobby):
    """Used to manage game rooms."""

    def __init__(self, lobby_info):
        # Call the superconstructor.
        super().__init__(lobby_info)

    # OVERRIDES Lobby.lobby_type()
    def lobby_type(self) -> LobbyType:
        return LobbyType.SCENARIO

    # OVERRIDES Lobby.get_leader_follower_match().
    def get_leader_follower_match(
        self,
    ) -> Tuple[web.WebSocketResponse, web.WebSocketResponse, str]:
        """Scenario lobbies only have one player, so we just return that player."""
        # If there's no general players, a match can't be made.
        if len(self._player_queue) < 1:
            return None, None, ""

        (_, player, e_uuid) = self._player_queue.popleft()
        return None, player, e_uuid

    # OVERRIDES Lobby.handle_join_request().
    def handle_join_request(
        self, request: RoomManagementRequest, ws: web.WebSocketResponse
    ) -> None:
        """Handles a join request from a client."""
        logger.info(f"Received join request from {ws}.")
        self.join_player_queue(ws, request)

    # Overrides Lobby.handle_replay_request().
    def handle_replay_request(
        self, request: ReplayRequest, ws: web.WebSocketResponse
    ) -> None:
        ...
