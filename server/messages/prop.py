from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from mashumaro.mixins.json import DataClassJSONMixin

import server.card_enums as card_enums
from server.card_enums import Color, Shape
from server.hex import HecsCoord
from server.messages import action

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
    color: Color
    shape: Shape
    count: int
    selected: bool
    hidden: Optional[bool] = False  # Whether the client should cover the card.


@dataclass(frozen=True)
class SimpleConfig(DataClassJSONMixin):
    __slots__ = "asset_id"
    asset_id: int


@dataclass(frozen=True)
class Prop(DataClassJSONMixin):
    __slots__ = ("id", "prop_type", "prop_info", "card_init", "simple_init")
    id: int
    prop_type: PropType
    prop_info: GenericPropInfo

    # Only one of these is populated, depending on this prop's prop_type.
    card_init: Optional[CardConfig]  # Only used for Card props.
    simple_init: Optional[SimpleConfig]  # Only used for Simple props.


@dataclass(frozen=True)
class PropUpdate(DataClassJSONMixin):
    props: List[Prop] = field(default_factory=list)

    @staticmethod
    def from_gym_state(observation):
        """Returns a PropUpdate from a given gym prop state."""
        props = []
        cards = observation["cards"]
        rows, cols = len(cards["counts"]), len(cards["counts"][0])
        # Only requirement for the card ID is that each ID is unique.
        card_id = 0
        for i in range(rows):
            for j in range(cols):
                location = HecsCoord.from_offset(i, j)
                rotation = 0
                border_color = card_enums.Color.BLUE
                count = cards["counts"][i][j]
                color = cards["colors"][i][j]
                border_color = cards["border_colors"][i][j]
                shape = cards["shapes"][i][j]
                selected = cards["selected"][i][j]
                prop_info = GenericPropInfo(
                    location=location,
                    rotation_degrees=rotation,
                    collide=False,
                    border_radius=0,
                    border_color=border_color,
                )
                card_init = CardConfig(
                    color=color, shape=shape, count=count, selected=selected
                )
                prop = Prop(
                    id=card_id,
                    prop_type=PropType.CARD,
                    prop_info=prop_info,
                    card_init=card_init,
                    simple_init=None,
                )
                props.append(prop)
                card_id += 1
        return PropUpdate(props=props)
