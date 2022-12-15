import logging

from peewee import Model
from playhouse.sqlite_ext import SqliteExtDatabase

logger = logging.getLogger(__name__)

database = SqliteExtDatabase(None)


class BaseModel(Model):
    class Meta:
        database = database  # Use proxy for our DB.


def SetDatabaseByPath(path):
    database.init(
        path,
        pragmas=[
            ("journal_mode", "wal"),
            ("cache_size", -1024 * 64),  # 64MB
            ("foreign_keys", 1),
            ("ignore_check_constraints", 0),
            ("synchronous", 1),
        ],
    )


def SetDatabase(config):
    logger.info(f"Pragmas: {config.sqlite_pragmas}")
    # Configure our proxy to use the db we specified in config.
    database.init(config.database_path(), pragmas=config.sqlite_pragmas)


def SetDatabaseForTesting():
    database.init(":memory:")


def ConnectDatabase():
    database.connect()


def GetDatabase():
    return database


def CloseDatabase():
    database.close()


def CreateTablesIfNotExists(tables):
    # Peewee injects an IF NOT EXISTS check in their create_tables command.
    # It's good to create a function name that explicitly mentions this.
    database.create_tables(tables)
