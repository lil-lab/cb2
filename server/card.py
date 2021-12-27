from enum import Enum
from hex import HecsCoord
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from messages.action import Action, ActionType, AnimationType

import datetime

import messages.prop


class Shape(Enum):
    NONE = 0
    PLUS = 1
    TORUS = 2
    HEART = 3
    DIAMOND = 4
    SQUARE = 5
    STAR = 6
    TRIANGLE = 7


class Color(Enum):
    NONE = 0
    BLACK = 1
    BLUE = 2
    GREEN = 3
    ORANGE = 4
    PINK = 5
    RED = 6
    YELLOW = 7


OUTLINE_RADIUS = 20


def CardSelectAction(card_id, selected):
    action_type = ActionType.OUTLINE
    radius = OUTLINE_RADIUS if selected else 0
    expiration = datetime.datetime.now() + datetime.timedelta(seconds=10)
    return Action(card_id, action_type, AnimationType.NONE, HecsCoord(0, 0, 0),
                  0, radius, 0.2, expiration)


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=False)
class Card:
    id: int
    location: HecsCoord
    rotation_degrees: int
    shape: Shape
    color: Color
    count: int
    selected: bool

    def prop(self):
        return messages.prop.Prop(self.id,
                                  messages.prop.PropType.CARD,
                                  messages.prop.GenericPropInfo(
                                      self.location, self.rotation_degrees, False, OUTLINE_RADIUS),
                                  messages.prop.CardConfig(
                                      self.color,
                                      self.shape,
                                      self.count,
                                      self.selected),
                                  None)
