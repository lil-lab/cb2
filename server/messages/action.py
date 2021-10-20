from enum import Enum
from hex import HecsCoord

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields

class ActionType(Enum):
    INSTANT = 0
    ROTATE = 1
    TRANSLATE = 2

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
    actor_id: int
    action_type: ActionType
    animation_type: AnimationType
    start: HecsCoord
    destination: HecsCoord
    start_heading: float
    destination_heading: float
    duration_s: float
    expiration: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=datetime.fromisoformat,
            mm_field=fields.DateTime(format='iso')
        ))
