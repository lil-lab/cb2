from config.config import Config
from map_tools.visualize import *
from playhouse.sqlite_ext import CSqliteExtDatabase
from schemas import base

import config.config as config

import fire

def BackupDb(config):
    database = CSqliteExtDatabase(config.database_path(), pragmas =
            [ ('cache_size', -1024 * 64),  # 64MB page-cache.
              ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
              ('foreign_keys', 1)])
    database.backup_to_file(config.backup_database_path())

def main(config_path="config/server-config.json"):
    """ Performs an online backup of the game database (works even if the server is actively running). """
    cfg = config.ReadConfigOrDie(config_path)
    BackupDb(cfg)

if __name__ == "__main__":
    fire.Fire(main)
