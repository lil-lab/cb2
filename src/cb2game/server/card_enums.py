from enum import Enum


class Shape(Enum):
    """Shapes that can be found on a card."""

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
    """Possible colors of the shapes on a card."""

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
    """Possible selection states a card can be in."""

    NONE = 0
    UNSELECTED = 1
    SELECTED = 2
    SELECTED_ERROR = 3  # Card is selected, but set completion rules are violated.
    MAX = 4
