from dataclasses import dataclass

import orjson
from mashumaro.mixins.json import DataClassJSONMixin
from peewee import TextField

from cb2game.server.hex import HecsCoord, LegacyHecsCoord


class HecsCoordField(TextField):
    def __init__(self, null=False):
        super(__class__, self).__init__(null=null)

    def db_value(self, value):
        if value is None:
            return None
        return orjson.dumps(value, option=orjson.OPT_NAIVE_UTC).decode("utf-8")

    def python_value(self, db_val):
        if db_val is None:
            return None
        try:
            return HecsCoord.from_json(db_val)
        except Exception:
            try:
                return HecsCoord.from_legacy(LegacyHecsCoord.from_json(db_val))
            except Exception:
                return None


@dataclass(frozen=True)
class InitialState(DataClassJSONMixin):
    leader_id: int  # In-game ID of the leader.
    follower_id: int  # In-game ID of the follower.
    leader_position: HecsCoord
    leader_rotation_degrees: int
    follower_position: HecsCoord
    follower_rotation_degrees: int
