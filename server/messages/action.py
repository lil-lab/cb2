import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from dateutil import tz
from mashumaro import pass_through
from mashumaro.mixins.json import DataClassJSONMixin

from server.hex import HecsCoord

logger = logging.getLogger()

DEFAULT_WALK_TIME_S = 0.45
DEFAULT_TURN_TIME_S = 0.33


class ActionType(Enum):
    INIT = 0
    INSTANT = 1
    ROTATE = 2
    TRANSLATE = 3
    OUTLINE = 4
    DEATH = 5
    NONE = 6


class AnimationType(Enum):
    NONE = 0
    IDLE = 1
    WALKING = 2
    INSTANT = 3
    TRANSLATE = 4
    ACCEL_DECEL = 5
    SKIPPING = 6
    ROTATE = 7


@dataclass(frozen=True)
class Color(DataClassJSONMixin):
    r: float
    g: float
    b: float
    a: float

    def __eq__(self, rhs):
        return (
            self.r == rhs.r and self.g == rhs.g and self.b == rhs.b and self.a == rhs.a
        )


def CensorActionForFollower(action, follower):
    """Censors actions to hide information that followers aren't supposed to see.

    For now, replaces red border colors with blue.
    """
    if action.border_color == Color(1, 0, 0, 1):
        action = replace(action, border_color=Color(0, 0, 1, 1))
        logger.debug(f"Censored action {action} for follower {follower}")
    return action


@dataclass(frozen=True)
class Action(DataClassJSONMixin):
    id: int = "-1"
    action_type: ActionType = ActionType.NONE
    animation_type: AnimationType = AnimationType.NONE
    # Displacement is used in TRANSLATE, INIT, and INSTANT actions.
    displacement: HecsCoord = HecsCoord.origin()
    # For rotations. In Degrees.
    rotation: float = 0.0
    border_radius: float = 0.0
    border_color: Color = Color(0, 0, 0, 0)
    duration_s: float = 0.0
    expiration: datetime = field(
        metadata={"deserialize": "pendulum", "serialize": pass_through},
        # Default to min time.
        default_factory=lambda: datetime.isoformat(
            datetime.min.replace(tzinfo=tz.tzutc())
        ),
    )
    border_color_follower_pov: Optional[Color] = None  # From follover's point of view.


def Delay(id, duration):
    return Action(
        id=id,
        action_type=ActionType.INSTANT,
        animation_type=AnimationType.INSTANT,
        displacement=HecsCoord.origin(),
        rotation=0,
        border_radius=0,
        border_color=Color(0, 0, 0, 0),
        duration_s=duration,
        expiration=datetime.utcnow() + timedelta(seconds=10),
    )


def Init(id, location, orientation):
    return Action(
        id=id,
        action_type=ActionType.INIT,
        animation_type=AnimationType.IDLE,
        displacement=location,
        rotation=orientation,
        border_radius=0,
        border_color=Color(0, 0, 0, 0),
        duration_s=0.01,
        expiration=datetime.utcnow() + timedelta(seconds=10),
    )


def Turn(id, angle, duration=DEFAULT_TURN_TIME_S):
    return Action(
        id=id,
        action_type=ActionType.ROTATE,
        animation_type=AnimationType.ROTATE,
        displacement=HecsCoord.origin(),
        rotation=angle,
        border_radius=0,
        border_color=Color(0, 0, 0, 0),
        duration_s=duration,
        expiration=datetime.utcnow() + timedelta(seconds=10),
    )


def Walk(id, displacement, duration=DEFAULT_WALK_TIME_S):
    return Action(
        id=id,
        action_type=ActionType.TRANSLATE,
        animation_type=AnimationType.WALKING,
        displacement=displacement,
        rotation=0,
        border_radius=0,
        border_color=Color(0, 0, 0, 0),
        duration_s=duration,
        expiration=datetime.utcnow() + timedelta(seconds=10),
    )
