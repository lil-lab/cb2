from enum import Enum
from hex import HecsCoord
import card

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from messages import action
from typing import Optional

import dateutil.parser


class PropType(Enum):
    NONE = 0
    SIMPLE = 1
    CARD = 2


@dataclass_json
@dataclass
class GenericPropInfo:
    location: HecsCoord
    rotation_degrees: int
    collide: bool
    border_radius: int
    border_color: action.Color = action.Color(0, 0, 1, 1)


@dataclass_json
@dataclass(frozen=True)
class CardConfig:
    color: card.Color
    shape: card.Shape
    count: int
    selected: bool


@dataclass_json
@dataclass(frozen=True)
class SimpleConfig:
    asset_id: int


@dataclass_json
@dataclass(frozen=True)
class Prop:
    id: int
    prop_type: PropType
    prop_info: GenericPropInfo

    # Only one of these is populated, depending on this prop's prop_type.
    card_init: Optional[CardConfig]  # Only used for Card props.
    simple_init: Optional[SimpleConfig]  # Only used for Simple props.
