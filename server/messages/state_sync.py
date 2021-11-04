from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from hex import HecsCoord
from marshmallow import fields
from typing import List, Optional

import datetime
import dateutil.parser
import typing


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class Actor:
    actor_id: int
    asset_id: int
    location: HecsCoord
    rotation_degrees: int

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class StateSync:
    population: int
    actors: List[Actor]
    player_id: int = -1