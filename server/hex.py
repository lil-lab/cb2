""" Utility file handling hex-related calculations. """

from dataclasses import dataclass
from dataclasses_json import dataclass_json, LetterCase

# HECS-style coordinate class.
# https://en.wikipedia.org/wiki/Hexagonal_Efficient_Coordinate_System
@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class HecsCoord:
    a: int
    r: int
    c: int

@dataclass_json
@dataclass(frozen=True)
class HexBoundary:
    _edges: int

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class HexCell:
    coord: HecsCoord
    boundary: HexBoundary
    height: float
    layer: int