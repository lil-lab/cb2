import orjson
from peewee import *

import cb2game
from cb2game.server.messages.map_update import MapUpdate
from cb2game.server.schemas.game import *
from cb2game.server.schemas.mturk import *


def CamelCaseToSnakeCase(string_a: str) -> str:
    """Converts a CamelCase string to a snake_case string."""
    out = ""
    for i, c in enumerate(string_a):
        if c.isupper():
            if i > 0:
                out += "_"
            out += c.lower()
        else:
            out += c
    return out


def ConvertLegacyKeys(data: object):
    """We converted a lot of our json keys to be snake_case instead of CamelCase.

    This function converts the old CamelCase keys to snake_case.
    """
    # Convert the dictionary keys to snake_case.
    new_data = {}
    for key, value in data.items():
        new_key = CamelCaseToSnakeCase(key)
        # If the value is a dictionary or list, recursively convert the keys.
        if isinstance(value, dict):
            value = ConvertLegacyKeys(value)
        elif isinstance(value, list):
            # Only convert items in the list if they are dictionaries.
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    value[i] = ConvertLegacyKeys(item)
        new_data[new_key] = value
    return new_data


class MapUpdateField(TextField):
    def db_value(self, value):
        return orjson.dumps(value, option=orjson.OPT_NAIVE_UTC).decode("utf-8")

    def python_value(self, db_val):
        if db_val is None:
            return None
        try:
            return cb2game.server.messages.map_update.MapUpdate.from_json(db_val)
        except:
            parsed = json.loads(db_val)
            converted_data = ConvertLegacyKeys(parsed)
            serialized = json.dumps(converted_data)
            return cb2game.server.messages.map_update.MapUpdate.from_json(serialized)


class MapUpdate(BaseModel):
    world_seed = TextField()
    map_data = MapUpdateField()
    game = ForeignKeyField(Game, backref="map_updates", null=True)
    map_update_number = IntegerField()
    time = DateTimeField(default=datetime.datetime.utcnow)
