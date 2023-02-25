"""Possible rotations in CerealBar 2."""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from typing import List


class Rotation(str, Enum):
    """Rotations in the environment."""

    NORTHEAST: str = "NORTHEAST"
    NORTHWEST: str = "NORTHWEST"
    SOUTHEAST: str = "SOUTHEAST"
    SOUTHWEST: str = "SOUTHWEST"
    EAST: str = "EAST"
    WEST: str = "WEST"

    def shorthand(self) -> str:
        if self == Rotation.NORTHEAST:
            return "NE"
        elif self == Rotation.EAST:
            return "EAST"
        elif self == Rotation.SOUTHEAST:
            return "SE"
        elif self == Rotation.SOUTHWEST:
            return "SW"
        elif self == Rotation.WEST:
            return "WEST"
        elif self == Rotation.NORTHWEST:
            return "NW"
        else:
            raise ValueError("Could not convert: " + str(self))

    def __str__(self):
        return self.value

    def __hash__(self):
        return self.value.__hash__()

    def __int__(self) -> int:
        if self == Rotation.NORTHEAST:
            return 30
        elif self == Rotation.EAST:
            return 90
        elif self == Rotation.SOUTHEAST:
            return 150
        elif self == Rotation.SOUTHWEST:
            return 210
        elif self == Rotation.WEST:
            return 270
        elif self == Rotation.NORTHWEST:
            return 330
        else:
            raise ValueError("Could not convert: " + str(self))

    def to_radians(self) -> float:
        # First, make it point right
        offset_deg: int = (int(self) - 90 + 360) % 360

        # Then convert to radians
        return np.deg2rad(offset_deg)

    def to_v3(self) -> str:
        return f"0,{int(self)},0"


def degree_to_rotation(degree: int) -> Rotation:
    """Maps from an integer degree rotation given by Unity to a Rotation type.

    Input:
        degree (int): An integer degree rotation from Unity.

    Returns:
        The corresponding Rotation.

    Raises:
        ValueError, if the degree integer is not in the range (30 + 60x), where x is an integer in [0, 5].
    """
    if degree == 30:
        return Rotation.NORTHEAST
    elif degree == 90:
        return Rotation.EAST
    elif degree == 150:
        return Rotation.SOUTHEAST
    elif degree == 210:
        return Rotation.SOUTHWEST
    elif degree == 270:
        return Rotation.WEST
    elif degree == 330:
        return Rotation.NORTHWEST
    else:
        raise ValueError("Degree not in 30+60x; " + str(degree))


def rotation_from_v3(v3: str) -> Rotation:
    return degree_to_rotation(int(float(eval(v3)[1])))


ROTATIONS: List[Rotation] = [
    Rotation.NORTHEAST,
    Rotation.EAST,
    Rotation.SOUTHEAST,
    Rotation.SOUTHWEST,
    Rotation.WEST,
    Rotation.NORTHWEST,
]
