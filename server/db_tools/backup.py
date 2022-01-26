from config.config import Config
from map_tools.visualize import *
from playhouse.sqlite_ext import CSqliteExtDatabase
from schemas import base

import fire

# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    with open(config_path, 'r') as cfg_file:
        config = Config.from_json(cfg_file.read())
        return config

def BackupDb(config):
    database = CSqliteExtDatabase(config.database_path(), pragmas =
            [ ('cache_size', -1024 * 64),  # 64MB page-cache.
              ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
              ('foreign_keys', 1)])
    database.backup_to_file(config.backup_database_path())

def main(config_path="config/server-config.json"):
    """ Performs an online backup of the game database (works even if the server is actively running). """
    config = ReadConfigOrDie(config_path)
    BackupDb(config)

if __name__ == "__main__":
    fire.Fire(main)
