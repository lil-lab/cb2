import orjson
from peewee import *

from server.lobby_consts import *


class LobbyTypeField(TextField):
    def db_value(self, value):
        return orjson.dumps(value).decode("utf-8")

    def python_value(self, db_val):
        db_val_integer = int(db_val)
        return LobbyType(db_val_integer)
