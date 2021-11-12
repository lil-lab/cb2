from enum import Enum
from hex import HecsCoord
from card import Shape, Color

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields

import dateutil.parser


class PropType(Enum):
    NONE = 0
    SIMPLE = 1
    CARD = 2


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class GenericPropInfo:
    location: HecsCoord
    rotation_degrees: int
    collide: bool
    border_radius: int


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class CardConfig:
    color: Color
    shape: Shape
    count: int
    selected: bool


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class SimpleConfig:
    asset_id: int


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class Prop:
    id: int
    prop_type: PropType
    prop_info: GenericPropInfo

    # Only one of these is populated, depending on this prop's prop_type.
    card_init: CardConfig  # Only used for Card props.
    simple_init: SimpleConfig  # Only used for Simple props.
