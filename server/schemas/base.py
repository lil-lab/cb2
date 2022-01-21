from peewee import *

database = SqliteDatabase(None)  # Create a proxy for our db.

class BaseModel(Model):
    class Meta:
        database = database  # Use proxy for our DB.

def SetDatabase(db_path):
    # Configure our proxy to use the db we specified in config.
    database.init(db_path, pragmas = [('foreign_keys', 'on')])

def ConnectDatabase():
    database.connect()

def CreateTablesIfNotExists(tables):
    # Peewee injects an IF NOT EXISTS check in their create_tables command.
    # It's good to create a function name that explicitly mentions this.
    database.create_tables(tables)