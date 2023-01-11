""" A Lobby that's used for FMRI scenarios. """
import logging
from queue import Queue
from typing import Tuple

from aiohttp import web

import server.lobby as lobby
from server.lobby import LobbyType
from server.messages.replay_messages import ReplayRequest
from server.messages.rooms import RoomManagementRequest
from server.messages.scenario import (
    ScenarioRequest,
    ScenarioRequestType,
    ScenarioResponse,
    ScenarioResponseType,
)

logger = logging.getLogger(__name__)


class ScenarioLobby(lobby.Lobby):
    """Used to manage game rooms."""

    def __init__(self, lobby_name, lobby_comment):
        # Call the superconstructor.
        super().__init__(lobby_name=lobby_name, lobby_comment=lobby_comment)

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
        return player, None, e_uuid

    # OVERRIDES Lobby.handle_join_request().
    def handle_join_request(
        self, request: RoomManagementRequest, ws: web.WebSocketResponse
    ) -> None:
        """Handles a join request from a client."""
        ...

    # Overrides Lobby.handle_replay_request().
    def handle_replay_request(
        self, request: ReplayRequest, ws: web.WebSocketResponse
    ) -> None:
        ...

    # Overrides Lobby.handle_scenario_request()
    def handle_scenario_request(
        self, request: ScenarioRequest, ws: web.WebSocketResponse
    ) -> None:
        """Handles a request to join a replay room. In most lobbies, this should be ignored (except lobbies supporting replay)."""
        if ws not in self._pending_scenario_messages:
            self._pending_scenario_messages[ws] = Queue()

        if request.type in [
            ScenarioRequestType.OPEN_SCENARIO_WORLD,
            ScenarioRequestType.LOAD_SCENARIO,
        ]:
            # If LOAD_SCENARIO, pass in the scenario state to create_scenario.
            scenario = None
            if request.type == ScenarioRequestType.LOAD_SCENARIO:
                scenario = request.scenario_data
            self.create_scenario(ws, request.game_id, scenario)
            # Send a confirmation message.
            self._pending_scenario_messages[ws].put(
                ScenarioResponse(
                    ScenarioResponseType.LOADED,
                )
            )
        else:
            logger.warning(
                f"Room manager received incorrect scenario request type {request.type}."
            )
