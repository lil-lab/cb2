import asyncio
import hashlib
import logging
import os
import pathlib
from datetime import datetime
from enum import Enum

import orjson
import peewee

import cb2game.server.schemas.clients as clients_db
import cb2game.server.schemas.mturk as mturk_db
from cb2game.server.config.config import GlobalConfig
from cb2game.server.demo_state import DemoState
from cb2game.server.lobby_consts import IsGoogleLobby, IsMturkLobby
from cb2game.server.messages.logs import (
    LogEntryFromIncomingMessage,
    LogEntryFromOutgoingMessage,
)
from cb2game.server.messages.rooms import Role
from cb2game.server.messages.scenario import Scenario
from cb2game.server.messages.tutorials import RoleFromTutorialName
from cb2game.server.messages.user_info import UserType
from cb2game.server.remote_table import GetRemote
from cb2game.server.replay_state import ReplayState
from cb2game.server.scenario_state import ScenarioState
from cb2game.server.schemas.google_user import GetOrCreateGoogleUser
from cb2game.server.state import State
from cb2game.server.state_machine_driver import StateMachineDriver
from cb2game.server.tutorial_state import TutorialGameState

logger = logging.getLogger(__name__)


class RoomType(Enum):
    NONE = 0
    TUTORIAL = 1
    GAME = 2
    PRESET_GAME = 3  # Resuming from historical record.
    REPLAY = 4  # Serve game events live to the client for replay.
    SCENARIO = 5  # Game type for scenario rooms
    DEMO = 6  # Used for conferences.


class Room(object):
    """Represents a game room."""

    def __init__(
        self,
        name: str,
        max_players: int,
        game_id: int,
        game_record,
        lobby,
        room_type: RoomType = RoomType.GAME,
        tutorial_name: str = "",
        from_event_uuid: str = "",
    ):
        """from_event_uuid is the UUID of an event to start the game from."""
        self._name = name
        self._max_players = max_players
        self._players = []
        self._player_endpoints = []
        self._id = game_id
        self._room_type = room_type
        self._game_record = game_record
        self._lobby = lobby
        self._initialized = False  # Set to True at the bottom of this method.
        logger.info(
            f"Lobby object: {lobby} | name: {lobby.lobby_name()} | lobby type: {lobby.lobby_type()} | typeinfo: {type(lobby)}"
        )

        is_mturk = IsMturkLobby(lobby.lobby_type())
        game_type_prefix = f"{lobby.lobby_name()}|{lobby.lobby_type()}|"

        if self._room_type == RoomType.GAME:
            if is_mturk:
                self._game_record.type = f"{game_type_prefix}game-mturk"
            else:
                self._game_record.type = f"{game_type_prefix}game"
            game_state = State(
                self._id, self._game_record, realtime_actions=True, lobby=lobby
            )
        elif self._room_type == RoomType.TUTORIAL:
            if RoleFromTutorialName(tutorial_name) == Role.LEADER:
                self._game_record.type = game_type_prefix + "lead_tutorial"
            else:
                self._game_record.type = game_type_prefix + "follow_tutorial"
            game_state = TutorialGameState(
                self._id, tutorial_name, self._game_record, True, self._lobby
            )
        elif self._room_type == RoomType.PRESET_GAME:
            if not from_event_uuid:
                raise ValueError("Preset game must be initialized from an instruction.")
            game_state, reason = State.InitializeFromExistingState(
                self._id, from_event_uuid, True, lobby=lobby
            )
            if game_state is None:
                logger.warning(f"Failed to initialize game from instruction: {reason}")
                return
        elif self._room_type == RoomType.REPLAY:
            game_state = ReplayState(self._id, self._game_record)
        elif self._room_type == RoomType.DEMO:
            game_state = DemoState(self._id)
        elif self._room_type == RoomType.SCENARIO:
            self._game_record.type = f"{game_type_prefix}scenario"
            game_state = ScenarioState(
                self._id, self._game_record, realtime_actions=True, lobby=lobby
            )
        else:
            game_state = None
            logger.error(f"Room started with invalid type {self._room_type}.")
            return
        self._state_machine_driver = StateMachineDriver(
            game_state, self._id, self._lobby
        )
        if self._room_type not in [
            RoomType.PRESET_GAME,
            RoomType.REPLAY,
            RoomType.DEMO,
        ]:
            self._game_record.save()
        self._update_loop = None
        if self._room_type == RoomType.PRESET_GAME:
            # Create a dummy log directory for the game that ignores all writes.
            self._log_directory = pathlib.Path(os.devnull)
            # Create a dummy file object that ignores all bytes.
            self._messages_from_server_log = open(os.devnull, "w")
            self._messages_to_server_log = open(os.devnull, "w")
        elif self._room_type in [RoomType.REPLAY, RoomType.DEMO]:
            # Create a dummy log directory for the game that ignores all writes.
            self._log_directory = pathlib.Path(os.devnull)
            # Create a dummy file object that ignores all bytes.
            self._messages_from_server_log = open(os.devnull, "w")
            self._messages_to_server_log = open(os.devnull, "w")
        else:
            log_directory = pathlib.Path(game_record.log_directory)
            if not os.path.exists(log_directory):
                logger.warning(
                    "Provided log directory does not exist. Game will not be recorded."
                )
                return
            self._log_directory = log_directory
            messages_from_server_path = pathlib.Path(
                self._log_directory, "messages_from_server.jsonl.log"
            )
            self._messages_from_server_log = messages_from_server_path.open("w")
            messages_to_server_path = pathlib.Path(
                self._log_directory, "messages_to_server.jsonl.log"
            )
            self._messages_to_server_log = messages_to_server_path.open("w")

        # Write the current server config to the log_directory as config.json.
        if self._room_type not in [
            RoomType.PRESET_GAME,
            RoomType.REPLAY,
            RoomType.DEMO,
        ]:
            with open(pathlib.Path(self._log_directory, "config.json"), "w") as f:
                server_config = GlobalConfig()
                if server_config is not None:
                    f.write(orjson.dumps(server_config).decode("utf-8"))

        self._map_update_count = 0
        self._initialized = True

    def initialized(self):
        return self._initialized

    def game_record(self):
        return self._game_record

    def add_player(self, ws, role):
        """Adds a player to the room."""
        if self.is_full():
            raise ValueError("Room is full.")
        state_machine = self._state_machine_driver.state_machine()
        id = state_machine.create_actor(role)
        remote = GetRemote(ws)

        # Fetch the leader and follower user information.
        if remote != None and self._room_type not in [
            RoomType.PRESET_GAME,
            RoomType.DEMO,
        ]:
            # If mturk..
            is_mturk = IsMturkLobby(self._lobby.lobby_type())
            is_google = IsGoogleLobby(self._lobby.lobby_type())
            if is_mturk:
                remote_record = (
                    clients_db.Remote.select()
                    .join(mturk_db.Worker, join_type=peewee.JOIN.LEFT_OUTER)
                    .where(
                        clients_db.Remote.hashed_ip == remote.hashed_ip,
                        clients_db.Remote.remote_port == remote.client_port,
                    )
                    .get()
                )
                if remote_record is None:
                    logger.error(
                        f"Added player with unrecognized remote IP(md5 hash)/Port: {remote.hashed_ip}/{remote.client_port}"
                    )
                if role == Role.LEADER:
                    self._game_record.lead_remote = remote_record
                    if (remote_record is not None) and (
                        remote_record.assignment is not None
                    ):
                        self._game_record.lead_assignment = remote_record.assignment
                        self._game_record.leader = remote_record.worker
                else:
                    self._game_record.follow_remote = remote_record
                    if (
                        remote_record is not None
                    ) and remote_record.assignment is not None:
                        self._game_record.follow_assignment = remote_record.assignment
                        self._game_record.follower = remote_record.worker
            elif is_google and remote.user_type == UserType.GOOGLE:
                google_id = remote.google_id
                # SHA256 hash of the google id.
                hashed_google_id = hashlib.sha256(google_id.encode("utf-8")).hexdigest()
                if role == Role.LEADER:
                    self._game_record.google_leader = GetOrCreateGoogleUser(
                        hashed_google_id
                    )
                else:
                    self._game_record.google_follower = GetOrCreateGoogleUser(
                        hashed_google_id
                    )
            self._game_record.save()
        else:
            logger.warning(f"Starting room without remote IP/Port/Google information.")
        self._players.append(id)
        self._player_endpoints.append(ws)
        return id

    def remove_player(self, id, ws, disconnected=False):
        """Removes a player from the room. Optionally mark the player as abandoning the game due to disconnect."""
        if id not in self._players:
            logger.error(
                f"Attempted to remove player {id} from room {self._id} but player was not in room."
            )
            return
        self._players.remove(id)
        if ws in self._player_endpoints:
            self._player_endpoints.remove(ws)
        self._state_machine_driver.state_machine().free_actor(id)
        if disconnected:
            self._state_machine_driver.state_machine().mark_player_disconnected(id)

    def player_endpoints(self):
        return self._player_endpoints

    def player_role(self, player_id):
        return self._state_machine_driver.state_machine().player_role(player_id)

    def number_of_players(self):
        return len(self._players)

    def drain_messages(self, id, messages):
        self._state_machine_driver.drain_messages(id, messages)
        # Log messages
        for message in messages:
            log_message = orjson.dumps(
                LogEntryFromIncomingMessage(id, message),
                option=orjson.OPT_NAIVE_UTC | orjson.OPT_PASSTHROUGH_DATETIME,
                default=datetime.isoformat,
            ).decode("utf-8")
            self._messages_to_server_log.write(log_message + "\n")
            logger.info(f"Received message type {message.type} for player {id}.")

    def start(self):
        if self._update_loop is not None:
            return RuntimeError("started Room that is already running.")

        self._update_loop = asyncio.create_task(self._state_machine_driver.run())
        logging.info(f"Room {self.id()} started game.")

    def scenario_id(self) -> str:
        return self._state_machine_driver.state_machine().scenario_id()

    def has_exception(self):
        return self._state_machine_driver.exception() is not None

    def exception(self):
        return self._state_machine_driver.exception()

    def traceback(self):
        return self._state_machine_driver.traceback()

    def stop(self):
        if self._update_loop is None:
            return RuntimeError("stopped Room that is not running.")
        logging.info(f"Room /{self.id()} ending game.")
        self._state_machine_driver.end_game()
        if not os.path.exists(self._log_directory):
            return
        self._messages_from_server_log.close()
        self._messages_to_server_log.close()

    def set_scenario(self, scenario: Scenario):
        self._state_machine_driver.state_machine().set_scenario(scenario)

    def done(self):
        if not self._initialized:
            return
        return self._state_machine_driver.done()

    def game_time(self):
        return self._state_machine_driver.state_machine().game_time()

    def has_pending_messages(self):
        return self._state_machine_driver.state_machine().has_pending_messages()

    def desync(self, id):
        self._state_machine_driver.state_machine().desync(id)

    def desync_all(self):
        self._state_machine_driver.state_machine().desync_all()

    def is_full(self):
        """Returns True if the room is full."""
        return len(self._players) == self._max_players

    def is_empty(self):
        """Returns True if the room is empty."""
        return len(self._players) == 0

    def state(self, actor_id=-1):
        return self._state_machine_driver.state_machine().state(actor_id)

    def selected_cards(self):
        return self._state_machine_driver.state_machine().selected_cards()

    def debug_status(self):
        is_done = self.done()
        turn_state = self._state_machine_driver.state_machine().turn_state()

        # Serialize state to json.
        turn_state_json = orjson.dumps(
            turn_state,
            option=orjson.OPT_PASSTHROUGH_DATETIME | orjson.OPT_INDENT_2,
            default=datetime.isoformat,
        ).decode("utf-8")

        return {
            "is_done": str(is_done),
            "turn_state": turn_state_json,
        }

    def fill_messages(self, player_id, out_messages):
        """Returns a MessageFromServer object to send to the indicated player.

        If no message is available, returns None.
        """
        messages = []
        if not self._state_machine_driver.fill_messages(player_id, messages):
            return False
        out_messages.extend(messages)

        for message in messages:
            try:
                log_bytes = orjson.dumps(
                    LogEntryFromOutgoingMessage(player_id, message),
                    option=orjson.OPT_NAIVE_UTC | orjson.OPT_PASSTHROUGH_DATETIME,
                    default=datetime.isoformat,
                ).decode("utf-8")
                self._messages_from_server_log.write(log_bytes + "\n")
            except TypeError:
                logger.info(f"Error with message {message}")
                while True:
                    import sys

                    sys.exit(1)
        return True

    def id(self):
        """Returns the room id."""
        return self._id

    def name(self):
        """Returns the room name."""
        return self._name

    def is_synced(self):
        return self._state_machine_driver.state_machine().is_synced()

    def is_synced(self, player_id):
        return self._state_machine_driver.state_machine().is_synced(player_id)
