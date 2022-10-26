from enum import Enum
from server.hex import HecsCoord
import server.card as card

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from mashumaro.mixins.json import DataClassJSONMixin
from datetime import datetime
from marshmallow import fields
from server.messages import action
from typing import List, Optional

import dateutil.parser

# TODO(sharf): This file is unnecessarily and prematurely abstracted. Props -> Cards, and simplify everything.

class PropType(Enum):
    NONE = 0
    SIMPLE = 1
    CARD = 2

@dataclass
class GenericPropInfo(DataClassJSONMixin):
    location: HecsCoord
    rotation_degrees: int
    collide: bool
    border_radius: int
    border_color: action.Color = action.Color(0, 0, 1, 1)
    border_color_follower: action.Color = action.Color(0, 0, 1, 1)


@dataclass
class CardConfig(DataClassJSONMixin):
    color: card.Color
    shape: card.Shape
    count: int
    selected: bool
    hidden: Optional[bool] = False # Whether the client should cover the card.


@dataclass(frozen=True)
class SimpleConfig(DataClassJSONMixin):
    __slots__ = ('asset_id')
    asset_id: int

@dataclass(frozen=True)
class Prop(DataClassJSONMixin):
    __slots__ = ('id', 'prop_type', 'prop_info', 'card_init', 'simple_init')
    id: int
    prop_type: PropType
    prop_info: GenericPropInfo

    # Only one of these is populated, depending on this prop's prop_type.
    card_init: Optional[CardConfig]  # Only used for Card props.
    simple_init: Optional[SimpleConfig]  # Only used for Simple props.

@dataclass(frozen=True)
class PropUpdate(DataClassJSONMixin):
    props: List[Prop] = field(default_factory=list)