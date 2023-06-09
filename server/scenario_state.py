import dataclasses
import logging
from datetime import datetime
from typing import List

from server.hex import HecsCoord
from server.map_provider import MapProvider, MapType
from server.map_utils import GroundTile, LayerToHeight
from server.messages import message_from_server, message_to_server
from server.messages.action import Init
from server.messages.map_update import MapMetadata, MapUpdate
from server.messages.rooms import Role
from server.messages.scenario import (
    Scenario,
    ScenarioRequest,
    ScenarioRequestType,
    ScenarioResponse,
    ScenarioResponseType,
)
from server.state import State

logger = logging.getLogger(__name__)

MAP_WIDTH = 25
MAP_HEIGHT = 25


def DefaultMap():
    """A small, empty map. Keep the player occupied until the scenario is loaded."""
    map_rows = []
    for r in range(0, MAP_HEIGHT):
        row = []
        for c in range(0, MAP_WIDTH):
            tile = GroundTile()
            row.append(tile)
        map_rows.append(row)

    # Fix all the tile coordinates.
    for r in range(0, MAP_HEIGHT):
        for c in range(0, MAP_WIDTH):
            map_rows[r][c].cell.coord = HecsCoord.from_offset(r, c)

    # Flatten the 2D map of tiles to a list.
    map_tiles = [tile for row in map_rows for tile in row]

    # Recompute heights.
    for i in range(len(map_tiles)):
        map_tiles[i].cell.height = LayerToHeight(map_tiles[i].cell.layer)

    map_metadata = MapMetadata([], [], [], [], 0)
    return MapUpdate(MAP_HEIGHT, MAP_WIDTH, map_tiles, map_metadata)


class ScenarioState(object):
    """This class wraps a state machine object and provides an interface for scenario messages to modify the state."""

    def __init__(
        self,
        room_id,
        game_record,
        log_to_db: bool = True,
        realtime_actions: bool = False,
        lobby: "server.Lobby" = None,
    ):
        self._room_id = room_id
        self._scenario_id = ""
        self._state = State(
            room_id,
            game_record,
            use_preset_data=False,
            log_to_db=log_to_db,
            realtime_actions=realtime_actions,
            lobby=lobby,
        )

        # Set the default map to all water. This locks the player in place and prevents movement. When a scenario is loaded, the map will be updated.
        self._state._map_provider = MapProvider(
            MapType.PRESET, DefaultMap(), []
        )  # pylint: disable=protected-access
        self._state._map_update = (
            self._state._map_provider.map()
        )  # pylint: disable=protected-access
        self._state._prop_update = (
            self._state._map_provider.prop_update()
        )  # pylint: disable=protected-access

        # Scenario messages that are queued for transmission. Per player.
        self._scenario_messages = {}  # {id: [message]}

    def game_time(self):
        return self._state.game_time()

    def end_game(self):
        self._state.end_game()

    def scenario_id(self):
        return self._scenario_id

    def mark_player_disconnected(self, id):
        self._state.mark_player_disconnected(id)

    def player_role(self, player_id):
        return self._state.player_role(player_id)

    def start(self):
        self._state.start()

    def done(self):
        return self._state.done()

    def turn_state(self):
        return self._state.turn_state()

    def player_ids(self):
        return self._state.player_ids()

    def update(self):
        self._state.update()

    def _find_player_of_role(self, role: Role):
        for player_id in self._state.player_ids():
            if self._state.player_role(player_id) == role:
                return player_id
        return None

    def on_game_over(self):
        self._state.on_game_over()

    def selected_cards(self):
        return self._state.selected_cards()

    def drain_messages(self, id, messages):
        for message in messages:
            self._drain_message(id, message)

    def _drain_message(self, id, message):
        if message.type == message_to_server.MessageType.SCENARIO_REQUEST:
            self._drain_scenario_request(id, message.scenario_request)
        else:
            self._state._drain_message(id, message)  # pylint: disable=protected-access

    def _drain_scenario_request(self, id: int, scenario_request: ScenarioRequest):
        if id not in self._scenario_messages:
            self._scenario_messages[id] = []
        if scenario_request.type == ScenarioRequestType.LOAD_SCENARIO:
            parsed_scenario = Scenario.from_json(scenario_request.scenario_data)
            logger.info(f"Received color_tint: {parsed_scenario.map.color_tint}")
            self._scenario_id = parsed_scenario.scenario_id
            # Modify turn_state turn_end time to be never...
            updated_turn_state = dataclasses.replace(
                parsed_scenario.turn_state, turn_end=datetime.max
            )
            parsed_scenario = dataclasses.replace(
                parsed_scenario, turn_state=updated_turn_state
            )
            self._state._set_scenario(
                parsed_scenario
            )  # pylint: disable=protected-access
            # Force a resync of all actor states.
            self._state.desync_all()
            self._state._mark_prop_stale()
            self._state._mark_map_stale()
            for monitor_id, _ in self._scenario_messages.items():
                self._scenario_messages[monitor_id].append(
                    ScenarioResponse(
                        type=ScenarioResponseType.LOADED,
                    )
                )
        elif scenario_request.type == ScenarioRequestType.END_SCENARIO:
            self._state.end_game()
        else:
            logger.error(f"Unknown scenario request type: {scenario_request.type}")

    def create_actor(self, role):
        created_id = self._state.create_actor(role)

        if role == Role.SPECTATOR:
            self._scenario_messages[created_id] = []
            return created_id

        actor = self._state._actors[created_id]  # pylint: disable=protected-access
        actor.add_action(
            Init(created_id, HecsCoord.from_offset(MAP_HEIGHT // 2, MAP_WIDTH // 2), 0)
        )
        actor.step()
        # log the actor location.
        self.desync_all()
        return created_id

    def free_actor(self, actor_id):
        if actor_id in self._scenario_messages:
            del self._scenario_messages[actor_id]

        self._state.free_actor(actor_id)

    def desync(self, actor_id):
        self._state.desync(actor_id)

    def desync_all(self):
        self._state.desync_all()

    def is_synced(self, actor_id):
        return self._state.is_synced(actor_id)

    def has_pending_messages(self):
        return self._state.has_pending_messages()

    def fill_messages(
        self, player_id, out_messages: List[message_from_server.MessageFromServer]
    ) -> bool:
        """Serializes all messages to one player into a linear history.

        If any messages have been generated this iteration, caps those
        messages with a StateMachineTick. This lets us separate logic
        iterations on the receive side.
        """
        message = self._next_message(player_id)
        messages_added = 0
        while message != None:
            out_messages.append(message)
            messages_added += 1
            message = self._next_message(player_id)
        if messages_added == 0:
            return False
        return True

    def _next_message(self, player_id):
        scenario_response = self._next_scenario_response(player_id)
        if scenario_response is not None:
            logger.debug(
                f"Room {self._room_id} has scenario response for player_id {player_id}"
            )
            msg = message_from_server.ScenarioResponseFromServer(scenario_response)
            return msg
        return self._state._next_message(player_id)  # pylint: disable=protected-access

    def _next_scenario_response(self, player_id):
        if player_id not in self._scenario_messages:
            return None
        if len(self._scenario_messages[player_id]) == 0:
            return None
        return self._scenario_messages[player_id].pop(0)

    # Returns the current state of the game.
    def state(self, actor_id=-1):
        return self._state.state(actor_id)
