""" Utility file handling hex-related calculations. """

from dataclasses import dataclass
from dataclasses_json import DataClassJsonMixin, dataclass_json, LetterCase
from mashumaro.mixins.json import DataClassJSONMixin
from enum import IntEnum

import math
import logging

logger = logging.getLogger()

# HECS-style coordinate class.
# https://en.wikipedia.org/wiki/Hexagonal_Efficient_Coordinate_System
@dataclass(frozen=True)
class HecsCoord(DataClassJSONMixin):
    a: int
    r: int
    c: int

    def origin():
        return HecsCoord(0, 0, 0)

    def from_offset(row, col):
        """ Converts Hex offset coordinates to HECS A, R, C coordinates. """
        return HecsCoord(row % 2, row // 2, col)
    
    # https://en.wikipedia.org/wiki/Hexagonal_Efficient_Coordinate_System#Addition
    def add(a, b):
        return HecsCoord(
            a.a ^ b.a,
			a.r + b.r + (a.a & b.a),
			a.c + b.c + (a.a & b.a));
    
    def sub(a, b):
        return HecsCoord.add(a, b.negate())
    
    def up_right(self):
        return HecsCoord(1 - self.a, self.r - (1 - self.a), self.c + self.a)
    
    def right(self):
        return HecsCoord(self.a, self.r, self.c + 1)
    
    def down_right(self):
        return HecsCoord(1 - self.a, self.r + self.a, self.c + self.a)
    
    def down_left(self):
        return HecsCoord(1 - self.a, self.r + self.a, self.c - (1 - self.a))
    
    def left(self):
        return HecsCoord(self.a, self.r, self.c - 1)
    
    def up_left(self):
        return HecsCoord(1 - self.a, self.r - (1 - self.a), self.c - (1 - self.a))
    
    def equals(self, other):
        return self.a == other.a and self.r == other.r and self.c == other.c
    
    def neighbors(self):
        return [
            self.up_right(),
            self.right(),
            self.down_right(),
            self.down_left(),
            self.left(),
            self.up_left()
        ]
        
    
    def degrees_to(self, other):
        """ Returns which direction (in degrees, nearest div of 60) to go from this Hecs coordinate to another Hecs coordinate. """
        c = self.cartesian()
        oc = other.cartesian()
        diff = (oc[0] - c[0], oc[1] - c[1])
        deg = math.degrees(math.atan2(diff[1], diff[0]))
        nearest_div_of_60 = round(deg / 60.0) * 60
        return nearest_div_of_60
    
    def distance_to(self, other):
        """ Returns the distance between this Hecs coordinate and another Hecs coordinate. """
        self_cart = self.cartesian()
        other_cart = other.cartesian()
        return math.sqrt((self_cart[0] - other_cart[0]) ** 2 + (self_cart[1] - other_cart[1]) ** 2)
    
    def is_adjacent_to(self, other):
        displacement = HecsCoord.sub(other, self)
        if abs(displacement.a) == 0:
            return (displacement.r == 0) and abs(displacement.c) == 1
        elif abs(displacement.a) == 1:
            return (displacement.r in [0, -1]) and (displacement.c in [0, -1])
        
        return False
    
    def neighbor_at_heading(self, heading):
        """  Returns the Hecs coordinate of the neighbor at a given heading.
        
        Heading is a floating point angle in degrees, indicating heading clockwise from true north. """
        neighbor_index = (int(heading / 60.0)) % 6
        if (neighbor_index < 0):
            neighbor_index += 6
        return self.neighbors()[neighbor_index];
    
    def cartesian(self):
        """ Calculate the cartesian coordinates of this Hecs coordinate. """
        return (0.5 * self.a + self.c, math.sqrt(3) / 2.0 * self.a + math.sqrt(3) * self.r)

    # https://en.wikipedia.org/wiki/Hexagonal_Efficient_Coordinate_System#Negation
    def negate(self):
        return HecsCoord(self.a, -self.r - self.a, -self.c - self.a);
    
    def to_offset_coordinates(self):
        """ Converts HECS A, R, C coordinates to Hex offset coordinates. """
        return (self.r * 2 + self.a, self.c)

@dataclass(frozen=True)
class Edges(IntEnum):
    UPPER_RIGHT = 0
    RIGHT = 1
    LOWER_RIGHT = 2
    LOWER_LEFT = 3
    LEFT = 4
    UPPER_LEFT = 5

@dataclass(unsafe_hash=True)
class HexBoundary(DataClassJSONMixin):
    edges: int

    DIR_TO_EDGE = {
        HecsCoord.origin().up_right(): Edges.UPPER_RIGHT,
        HecsCoord.origin().right(): Edges.RIGHT,
        HecsCoord.origin().down_right(): Edges.LOWER_RIGHT,
        HecsCoord.origin().down_left(): Edges.LOWER_LEFT,
        HecsCoord.origin().left(): Edges.LEFT,
        HecsCoord.origin().up_left(): Edges.UPPER_LEFT,
    }

    MAX_VAL = (Edges.UPPER_RIGHT | Edges.RIGHT | Edges.LOWER_RIGHT | Edges.LOWER_LEFT | Edges.LEFT | Edges.UPPER_LEFT)

    def rotate_cw(bound, rotation_degrees=0):
        # We can only rotate by even numbers of 60 degrees.
        turns = rotation_degrees // 60

        rotated = HexBoundary(bound.edges)
        rotated.rotate_clockwise(turns)
        return rotated


    def set_edge(self, edge):
        self.edges |= 1 << int(edge)
    
    def get_edge(self, edge):
        return (self.edges & 1 << int(edge)) != 0

    def has_edge(self, edge):
        return self.edges & (1 << int(edge)) != 0
    
    def opposite_edge(self, edge):
        return (edge + 3) % 6

    def rotate_clockwise(self, turns):
        for i in range(turns):
                        self.edges = ((self.edges << 1) | (self.edges >> 5)) & 0x3F

    def set_edge_between(self, a, b):
        """ Sets the edge between two HECS coordinates, if this cell is at location a and the neighbor is at location b. """
        displacement = HecsCoord.sub(b, a)
        edge = HexBoundary.DIR_TO_EDGE.get(displacement, None)
        if edge is None:
            raise ValueError(f"HecsCoords {a}, {b} passed to set_edge_between are not adjacent.")
        self.set_edge(edge)
    
    def get_edge_between(self, a, b):
        """ Checks the edge between two HECS coordinates, if this cell is at location a and the neighbor is at location b. """
        displacement = HecsCoord.sub(b, a)
        edge = HexBoundary.DIR_TO_EDGE.get(displacement, None)
        if edge is None:
            raise ValueError(f"HecsCoords {a}, {b} passed to set_edge_between are not adjacent.")
        return self.get_edge(edge)


@dataclass(unsafe_hash=True)
class HexCell(DataClassJSONMixin):
    coord: HecsCoord
    boundary: HexBoundary
    height: float
    layer: int