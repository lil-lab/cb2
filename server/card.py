from enum import Enum
from server.hex import HecsCoord
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from server.messages.action import Action, ActionType, AnimationType

import datetime
import random

import server.messages.prop as prop
import server.messages.action as action
from server.schemas.cards import CardSelections

from dateutil import tz

class Shape(Enum):
    NONE = 0
    PLUS = 1
    TORUS = 2
    HEART = 3
    DIAMOND = 4
    SQUARE = 5
    STAR = 6
    TRIANGLE = 7
    MAX = 8

class Color(Enum):
    NONE = 0
    BLACK = 1
    BLUE = 2
    GREEN = 3
    ORANGE = 4
    PINK = 5
    RED = 6
    YELLOW = 7
    MAX = 8

class SelectedState(Enum):
    NONE = 0
    UNSELECTED = 1
    SELECTED = 2
    SELECTED_ERROR = 3  # Card is selected, but set completion rules are violated.
    MAX = 4

OUTLINE_RADIUS = 30

# Returns a list of 3 tuples of (shape, color, count) that make up a unique sert of cards.
def RandomUniqueSet():
    shapes = [Shape.PLUS, Shape.TORUS, Shape.HEART, Shape.DIAMOND, Shape.SQUARE, Shape.STAR, Shape.TRIANGLE]
    colors = [Color.BLACK, Color.BLUE, Color.GREEN, Color.ORANGE, Color.PINK, Color.RED, Color.YELLOW]
    counts = [1, 2, 3]
    selected_shapes = random.sample(shapes, 3)
    selected_colors = random.sample(colors, 3)
    selected_counts = random.sample(counts, 3)
    return list(zip(selected_shapes, selected_colors, selected_counts))

# Returns a list of actions to animate card completion. First selects the cards
# in green, then triggers a blink animation.
def SetCompletionActions(card_id):
    actions = []
    green_color = action.Color(0, 1, 0, 1)
    return CardBlink(card_id, 2, 1, green_color)

def CardBlink(card_id, number_blinks, duration_s, color):
    blink_duration = duration_s / number_blinks
    blink_duty_cycle = 0.7
    blink_duration_on = blink_duration * blink_duty_cycle
    blink_duration_off = blink_duration - blink_duration_on
    return (number_blinks * [
        CardSelectAction(card_id, True, color, blink_duration_on),
        CardSelectAction(card_id, False, color, blink_duration_off),
    ])

def CardSelectAction(card_id, selected, color=action.Color(0, 0, 1, 1), duration_s=0.2):
    NYC = tz.gettz('America/New_York')
    action_type = ActionType.OUTLINE
    radius = OUTLINE_RADIUS if selected else 0
    expiration = datetime.datetime.now(NYC) + datetime.timedelta(seconds=10)
    return Action(card_id, action_type, AnimationType.NONE, HecsCoord(0, 0, 0),
                  0, radius, color, duration_s, expiration)


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
    border_color: action.Color = action.Color(0, 0, 1, 1)
    hidden: bool = False

    def __hash__(self):
        return hash(
            self.id,
            self.location,
            self.rotation_degrees,
            self.shape,
            self.color,
            self.count)

    @classmethod
    def FromProp(cls, prop):
        return cls(
            prop.id,
            prop.prop_info.location,
            prop.prop_info.rotation_degrees, 
            prop.card_init.shape,
            prop.card_init.color,
            prop.card_init.count,
            prop.card_init.selected,
            prop.prop_info.border_color,
            prop.card_init.hidden)
        
    def prop(self):
        return prop.Prop(
                        self.id,
                        prop.PropType.CARD,
                        prop.GenericPropInfo(
                            self.location, self.rotation_degrees, False, OUTLINE_RADIUS, self.border_color),
                        prop.CardConfig(
                            self.color,
                            self.shape,
                            self.count,
                            self.selected,
                            self.hidden),
                        None)
