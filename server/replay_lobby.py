""" A Lobby that's used for replay games. """
import logging
from queue import Queue
from typing import Tuple

from aiohttp import web

import server.lobby as lobby
from server.lobby import LobbyType
from server.messages.replay_messages import (
    ReplayRequest,
    ReplayRequestType,
    ReplayResponse,
    ReplayResponseType,
)
from server.messages.rooms import RoomManagementRequest

logger = logging.getLogger(__name__)


class ReplayLobby(lobby.Lobby):
    """Used to manage game rooms."""

    def __init__(self, lobby_name, lobby_comment):
        # Call the superconstructor.
        super().__init__(lobby_name=lobby_name, lobby_comment=lobby_comment)

    # OVERRIDES Lobby.lobby_type()
    def lobby_type(self) -> LobbyType:
        return LobbyType.REPLAY

    # OVERRIDES Lobby.get_leader_follower_match().
    def get_leader_follower_match(
        self,
    ) -> Tuple[web.WebSocketResponse, web.WebSocketResponse, str]:
        """Replay lobbies only have one player, so we just return that player."""
        # If there's no general players, a match can't be made.
        if len(self._player_queue) < 1:
            return None, None, ""

        (_, player, e_uuid) = self._player_queue.popleft()
        return player, None, e_uuid

    # OVERRIDES Lobby.handle_join_request().
    def handle_join_request(
        self, request: RoomManagementRequest, ws: web.WebSocketResponse
    ) -> None:
        """Handles a join request from a client."""
        ...

    # Overrides Lobby.handle_replay_request()
    def handle_replay_request(
        self, request: ReplayRequest, ws: web.WebSocketResponse
    ) -> None:
        """Handles a request to join a replay room. In most lobbies, this should be ignored (except lobbies supporting replay)."""
        if ws not in self._pending_replay_messages:
            self._pending_replay_messages[ws] = Queue()

        if request.type == ReplayRequestType.START_REPLAY:
            self.create_replay(ws, request.game_id)
            self._pending_replay_messages[ws].put(
                ReplayResponse(
                    ReplayResponseType.REPLAY_STARTED,
                )
            )
        else:
            logger.warning(
                f"Room manager received incorrect replay request type {request.type}."
            )
