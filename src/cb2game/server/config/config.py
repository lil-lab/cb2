""" Defines datastructures for configuring the CB2 server. """
import logging
import pathlib
from dataclasses import dataclass, field
from typing import List

import appdirs
import yaml
from mashumaro.mixins.json import DataClassJSONMixin

from cb2game.server.config.map_config import MapConfig
from cb2game.server.lobby_consts import LobbyInfo, LobbyType

logger = logging.getLogger(__name__)

g_config = None


def GlobalConfig():
    global g_config
    return g_config


def InitGlobalConfig(config_path):
    global g_config
    g_config = ReadConfigOrDie(config_path)


def SetGlobalConfig(config):
    global g_config
    g_config = config


def ValidateConfig(config):
    """Checks whether or not the provided configuration is valid. Doubles as documentation for how configs should be specified.

    Args:
        config: The configuration to validate.
    Returns:
        A tuple of (valid, reason) where valid is a boolean indicating whether or not the configuration is valid, and reason is a string describing why the configuration is invalid.
    """
    if len(config.name) == 0:
        return False, "Name is empty"
    # Check if data prefix exists as a directory.
    if not config.data_directory().is_dir():
        # Create the directory if it doesn't exist. Print a message to notify the user of this.
        config.data_directory().mkdir(parents=True, exist_ok=True)
        logger.info(
            f"//////////////// Created data directory {config.data_directory()} ////////////////"
        )
    # Check if the data prefix contains a game_data.db file. Log a warning if it doesn't.
    if not config.database_path().is_file():
        logger.warning(
            f"Record directory {config.database_path()} does not exist. This can happen if it's your first time running a new config. The program will just create a database for you."
        )
    # If game_records doesn't exist, log a warning but don't fail.
    if not config.record_directory().is_dir():
        logger.warning(
            f"Record directory {config.record_directory()} does not exist. This is okay, it's just a sign that the logged network packets may be missing. Or it's your first time running a config."
        )
    return True, ""


# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    """Reads a config file and returns a Config object."""
    with open(config_path, "r") as cfg_file:
        config = yaml.load(cfg_file, Loader=yaml.CLoader)
        # If the type of the resulting data isn't already a config, convert it.
        if not isinstance(config, Config):
            config = Config.from_dict(config)
        valid_config, reason = ValidateConfig(config)
        if not valid_config:
            raise ValueError(f"Config file is invalid: {reason}")
        return config


def ReadServerConfigOrDie(config_path):
    """An alias of ReadConfigOrDie that indicates it's specifically server config."""
    return ReadConfigOrDie(config_path)


@dataclass
class DataConfig(DataClassJSONMixin):
    name: str = ""  # The name of the config.
    sqlite_db_path: str = ""  # The path to the sqlite database.
    # Default settings. Safe for use with low-resource AWS server (4g ram,
    # 2vcpu). In this case, a t4g.medium instance.
    sqlite_pragmas: List[List[str]] = field(
        default_factory=lambda: [
            ("journal_mode", "wal"),
            ("cache_size", -1024 * 64),
            ("foreign_keys", "1"),
            ("synchronous", "off"),
        ]
    )


# For backwards compatibility, the members of this class are ordered by when
# they were added rather than by relevancy.
#
# Config files are now YAML instead of JSON! This doesn't change anything, as
# YAML is actually a superset of JSON. But it lets us add comments to our config
# files, which is much needed.
@dataclass
class Config(DataClassJSONMixin):
    name: str = ""  # The name of the config.

    # Data filepath configurations. All of these are relative to return value of user_data_dir() from appdirs.
    # If you leave data_prefix empty, then a folder under the appdirs user data directory will be used by default.
    data_prefix: str = ""  # Prefix added to the below data directories. (Can be used to store data on a different fs -- but that CAN HURT performance).
    record_directory_suffix: str = "game_records/"  # Where to store game recordings.
    assets_directory_suffix: str = (
        "assets/"  # Where to store asset resources. Currently unused.
    )
    database_path_suffix: str = (
        "game_data.db"  # Where to store the sqlite3 record database.
    )
    backup_db_path_suffix: str = "game_data.bk.db"

    # This is not a server configuration. They're data configurations. Once game
    # data is downloaded via server URL '/data/download', this property can be
    # used to specify which game IDs are used for analysis scripts.
    # For example, [[1, 3], [5, 6]] would include games 1, 2, 3, 5, and 6.
    analysis_game_id_ranges: List[List[int]] = field(default_factory=list)

    http_port: int = 8080

    map_cache_size: int = 500

    comment: str = ""

    # If true, then cards are rendered with covers. Covers block the follower
    # from seeing what's on the card, but are invisible/transparent to the
    # leader.
    # DEPRECATED: This is now ignored. Instead, card covers are per-card.
    # Lobbies can choose whether to add covers by default, and scenarios can
    # specify covers in the map.
    card_covers: bool = False

    # Everything is 100% visible if it's closer than fog_start units away.
    fog_start: int = 13
    # Everything is 100% opaque if it's farther than fog_end units away.
    fog_end: int = 20
    # RE fog: everything in between fog_start and fog_end is linearly
    # interpolated to make a smooth transition.

    # Client-side FPS limit. -1 means the browser controls frame rate to optimize performance.
    fps_limit: int = -1

    # The game ID to start all statistical/research calculations from (discard before this).
    analytics_since_game_id: int = -1

    live_feedback_enabled: bool = False  # Is leader live feedback enabled for games?
    """Deprecated. See live_feedback_enabled member in LobbyInfo struct."""

    # Default settings. Safe for use with low-resource AWS server (4g ram,
    # 2vcpu). In this case, a t4g.medium instance.
    sqlite_pragmas: List[List[str]] = field(
        default_factory=lambda: [
            ("journal_mode", "wal"),
            ("cache_size", -1024 * 64),
            ("foreign_keys", "1"),
            ("synchronous", "off"),
        ]
    )

    # Names of lobbies and lobby types.
    lobbies: List[LobbyInfo] = field(
        default_factory=lambda: [
            LobbyInfo("default", LobbyType.GOOGLE, "The default lobby.", 40),
            LobbyInfo(
                "open", LobbyType.OPEN, "Lobby open to anyone. -- No user info.", 40
            ),
            LobbyInfo(
                "delayed-feedback",
                LobbyType.OPEN,
                "Lobby open to anyone. -- No user info.",
                40,
                1,
                False,
                False,
                0,
                False,
                True,
            ),
            LobbyInfo(
                "dual-feedback",
                LobbyType.OPEN,
                "Lobby open to anyone. -- No user info.",
                40,
                1,
                False,
                False,
                0,
                True,
                True,
            ),
            LobbyInfo(
                "bot-sandbox", LobbyType.OPEN, "Open lobby intended for bots.", 40
            ),
            LobbyInfo("mturk-lobby", LobbyType.MTURK, "Lobby for MTurk workers.", 40),
            LobbyInfo(
                "follower-pilot-lobby",
                LobbyType.FOLLOWER_PILOT,
                "Lobby for MTurk follower pilot workers.",
                40,
            ),
            LobbyInfo(
                "replay-lobby", LobbyType.REPLAY, "Lobby for displaying replays.", 40
            ),
            LobbyInfo(
                "acl", LobbyType.REPLAY, "ACL demo lobby", 40, is_demo_lobby=True
            ),
            LobbyInfo(
                "scenario-lobby",
                LobbyType.SCENARIO,
                "Lobby for scenario experiments.",
                40,
                1,
                False,
                False,
                0,
                False,
                False,
                False,
                True,
            ),
            LobbyInfo(
                "scenario-lobby-button",
                LobbyType.SCENARIO,
                "Lobby for scenario experiments with buttons.",
                40,
                1,
                False,
                False,
                0,
                False,
                False,
                False,
                True,
                True,
            ),
            LobbyInfo(
                "eval-lobby",
                LobbyType.SCENARIO,
                "Lobby used for evaluating agents.",
                10,
            ),
            LobbyInfo(
                "google-leader-lobby",
                LobbyType.GOOGLE_LEADER,
                "Lobby for human-bot games. Humans authenticated by google.",
                40,
            ),
            LobbyInfo(
                "demo-lobby-1",
                LobbyType.OPEN,
                "DEMO LOBBY FOR STUDENTS",
                10,
            ),
            LobbyInfo(
                "demo-lobby-2",
                LobbyType.OPEN,
                "DEMO LOBBY FOR STUDENTS",
                10,
            ),
            LobbyInfo(
                "demo-lobby-3",
                LobbyType.OPEN,
                "DEMO LOBBY FOR STUDENTS",
                10,
            ),
            LobbyInfo(
                "demo-lobby-4",
                LobbyType.OPEN,
                "DEMO LOBBY FOR STUDENTS",
                10,
            ),
            LobbyInfo(
                "demo-lobby-5",
                LobbyType.OPEN,
                "DEMO LOBBY FOR STUDENTS",
                10,
            ),
            LobbyInfo(
                "demo-lobby-6",
                LobbyType.OPEN,
                "DEMO LOBBY FOR STUDENTS",
                10,
            ),
            LobbyInfo(
                "demo-lobby-7",
                LobbyType.OPEN,
                "DEMO LOBBY FOR STUDENTS",
                10,
            ),
            LobbyInfo(
                "demo-lobby-8",
                LobbyType.OPEN,
                "DEMO LOBBY FOR STUDENTS",
                10,
            ),
            LobbyInfo(
                "demo-lobby-9",
                LobbyType.OPEN,
                "DEMO LOBBY FOR STUDENTS",
                10,
            ),
            LobbyInfo(
                "demo-lobby-10",
                LobbyType.OPEN,
                "DEMO LOBBY FOR STUDENTS",
                10,
            ),
        ]
    )

    google_oauth_client_id: str = ""

    # Where exceptions are logged.
    exception_prefix: str = "exceptions/"

    map_config: MapConfig = field(default_factory=MapConfig)

    # The maximum number of exceptions to store in the database.
    max_client_exceptions: int = 100

    # The number of seconds between exception log dumps.
    exception_log_interval: int = 60

    # SHA512sum hash of the server access password.
    # If this is empty, then no password is required.
    # You can use the following command to generate a password:
    #
    # echo -n "password" | sha512sum
    #
    # Or use the python command:
    #
    #   import hashlib
    #   hashlib.sha512("password".encode("utf-8")).hexdigest()
    #
    # Any CB2 page which provides access to data or functionality which
    # should not be public should require this password.
    server_password_sha512: str = ""

    # Data path accessors that add the requisite data_prefix.
    def data_directory(self):
        # If data_prefix is None or empty string, use appdirs. Else use the prefix.
        if self.data_prefix is None or len(self.data_prefix) == 0:
            return pathlib.Path(appdirs.user_data_dir("cb2-game-dev")).expanduser()
        return pathlib.Path(self.data_prefix).expanduser()

    def record_directory(self):
        return pathlib.Path(
            self.data_directory(), self.record_directory_suffix
        ).expanduser()

    def assets_directory(self):
        return pathlib.Path(
            self.data_directory(), self.assets_directory_suffix
        ).expanduser()

    def database_path(self):
        return pathlib.Path(
            self.data_directory(), self.database_path_suffix
        ).expanduser()

    def backup_database_path(self):
        return pathlib.Path(
            self.data_directory(), self.backup_db_path_suffix
        ).expanduser()

    def exception_directory(self):
        return pathlib.Path(self.data_directory(), self.exception_prefix).expanduser()

    def data_config(self) -> DataConfig:
        return DataConfig(
            name=self.name,
            sqlite_db_path=self.database_path(),
            sqlite_pragmas=self.sqlite_pragmas,
        )
