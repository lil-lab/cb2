""" Defines datastructures for configuring the CB2 server. """
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from typing import List, Optional

import pathlib

# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    with open(config_path, 'r') as cfg_file:
        config = Config.from_json(cfg_file.read())
        return config

@dataclass_json
@dataclass
class Config:
    # Data filepath configurations.
    data_prefix: str = "./" # Prefix added to the below data directories. Can be used to store data on a different fs.
    record_directory_suffix: str = "game_records/" # Where to store game recordings.
    assets_directory_suffix: str = "assets/"  # Where to store asset resources.
    database_path_suffix: str = "game_data.db"  # Where to store the sqlite3 record database.
    backup_db_path_suffix: str = "game_data.bk.db"

    # Data path accessors that add the requisite data_prefix.
    def record_directory(self):
        return pathlib.Path(self.data_prefix, self.record_directory_suffix).expanduser()
    def assets_directory(self):
        return pathlib.Path(self.data_prefix, self.assets_directory_suffix).expanduser()
    def database_path(self):
        return pathlib.Path(self.data_prefix, self.database_path_suffix).expanduser()
    def backup_database_path(self):
        return pathlib.Path(self.data_prefix, self.backup_db_path_suffix).expanduser()

    http_port: int = 8080

    # Optional feature configurations.
    gui: bool = False