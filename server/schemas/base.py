from peewee import *
from playhouse.sqlite_ext import CSqliteExtDatabase

database = CSqliteExtDatabase(None)

class BaseModel(Model):
    class Meta:
        database = database  # Use proxy for our DB.

def SetDatabase(db_path):
    # Configure our proxy to use the db we specified in config.
    database.init(
        db_path, 
        pragmas =
            [ ('cache_size', -1024 * 64),  # 64MB page-cache. Negative implies kibibytes as units... yeah lol.
              ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
              ('foreign_keys', 1)]
    )

def ConnectDatabase():
    database.connect()

def CreateTablesIfNotExists(tables):
    # Peewee injects an IF NOT EXISTS check in their create_tables command.
    # It's good to create a function name that explicitly mentions this.
    database.create_tables(tables)