from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from hex import HecsCoord
from mashumaro.mixins.json import DataClassJSONMixin
from marshmallow import fields
from typing import List, Optional

import datetime
import dateutil.parser
import typing


@dataclass(frozen=True)
class Actor(DataClassJSONMixin):
    actor_id: int
    asset_id: int
    location: HecsCoord
    rotation_degrees: float

@dataclass(frozen=True)
class StateSync(DataClassJSONMixin):
    population: int
    actors: List[Actor]
    player_id: int = -1
