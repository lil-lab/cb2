""" Defines datastructures for configuring the CB2 server. """
import logging
import pathlib
from dataclasses import dataclass, field
from typing import List

import yaml
from mashumaro.mixins.json import DataClassJSONMixin

logger = logging.getLogger(__name__)

g_config = None


def GlobalConfig():
    global g_config
    return g_config


def InitGlobalConfig(config_path):
    global g_config
    g_config = ReadConfigOrDie(config_path)


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
        return False, f"Data prefix {config.data_directory()} is not a directory"
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
    with open(config_path, "r") as cfg_file:
        data = yaml.load(cfg_file, Loader=yaml.CLoader)
        config = Config.from_dict(data)
        valid_config, reason = ValidateConfig(config)
        if not valid_config:
            raise ValueError(f"Config file is invalid: {reason}")
        return config


# For backwards compatibility, the members of this class are ordered by when
# they were added rather than by relevancy.  This is unfortunate, I should
# probably group config members by category (analysis, server, database, etc)
# and then have a wrapper which breaks them out that way.
#
# Config files are now YAML instead of JSON! This doesn't change anything, as
# YAML is actually a superset of JSON. But it lets us add comments to our config
# files, which is much needed.
@dataclass
class Config(DataClassJSONMixin):
    name: str = ""  # The name of the config.

    # Data filepath configurations.
    data_prefix: str = "./"  # Prefix added to the below data directories. Can be used to store data on a different fs.
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

    # Optional feature configurations.
    gui: bool = False

    map_cache_size: int = 500

    comment: str = ""

    # If true, then cards are rendered with covers. Covers block the follower
    # from seeing what's on the card, but are invisible/transparent to the
    # leader.
    card_covers: bool = False

    # Everything is 100% visible if it's closer than fog_start units away.
    fog_start: int = 13
    # Everything is 100% opaque if it's farther than fog_end units away.
    fog_end: int = 20
    # RE fog: everything in between fog_start and fog_end is linearly
    # interpolated to make a smooth transition.

    # Client-side FPS limit. -1 means the browser controls frame rate to optimize performance.
    fps_limit: int = -1

    analytics_since_game_id: int = (
        -1
    )  # The game ID to start all statistical/research calculations from (discard before this).

    live_feedback_enabled: bool = True  # Is leader live feedback enabled for games?

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

    # Data path accessors that add the requisite data_prefix.
    def data_directory(self):
        return pathlib.Path(self.data_prefix).expanduser()

    def record_directory(self):
        return pathlib.Path(self.data_prefix, self.record_directory_suffix).expanduser()

    def assets_directory(self):
        return pathlib.Path(self.data_prefix, self.assets_directory_suffix).expanduser()

    def database_path(self):
        return pathlib.Path(self.data_prefix, self.database_path_suffix).expanduser()

    def backup_database_path(self):
        return pathlib.Path(self.data_prefix, self.backup_db_path_suffix).expanduser()
