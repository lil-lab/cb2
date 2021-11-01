from enum import Enum
from hex import HecsCoord

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields

import dateutil.parser

class ActionType(Enum):
    INIT = 0
    INSTANT = 1
    ROTATE = 2
    TRANSLATE = 3

class AnimationType(Enum):
    IDLE = 0
    WALKING = 1
    INSTANT = 2
    TRANSLATE = 3
    ACCEL_DECEL = 4
    SKIPPING = 5
    ROTATE = 6

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class Action:
    id: int
    action_type: ActionType
    animation_type: AnimationType
    displacement: HecsCoord
    rotation: float
    duration_s: float
    expiration: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=dateutil.parser.isoparse,
            mm_field=fields.DateTime(format='iso')
        ))
