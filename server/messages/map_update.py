import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List

from mashumaro.mixins.json import DataClassJSONMixin

from server.hex import HecsCoord, HexCell
from server.messages.prop import Prop

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Tile(DataClassJSONMixin):
    asset_id: int
    cell: HexCell
    rotation_degrees: int


@dataclass
class City(DataClassJSONMixin):
    r: int
    c: int
    size: int


class LakeType(Enum):
    """The type of lake to generate."""

    RANDOM = 0
    L_SHAPED = 1
    ISLAND = 2
    REGULAR = 3


@dataclass
class Lake(DataClassJSONMixin):
    r: int
    c: int
    size: int
    type: LakeType = LakeType.REGULAR


class MountainType(Enum):
    NONE = 0
    SMALL = 1
    MEDIUM = 2
    LARGE = 3


@dataclass
class Mountain(DataClassJSONMixin):
    r: int
    c: int
    type: MountainType
    snowy: bool


# A collection of 3-4 tiles that are path-connected (BFS) to two other features.
@dataclass
class Outpost(DataClassJSONMixin):
    r: int
    c: int
    connection_a: HecsCoord
    connection_b: HecsCoord
    tiles: List[Tile]  # Tiles. HECS coordinates will be ignored.


@dataclass
class MapMetadata(DataClassJSONMixin):
    lakes: List[Lake] = field(default_factory=list)
    mountains: List[Mountain] = field(default_factory=list)
    cities: List[City] = field(default_factory=list)
    outposts: List[Outpost] = field(default_factory=list)
    num_partitions: int = 0
    partition_locations: List[Tile] = field(default_factory=list)
    partition_sizes: List[int] = field(default_factory=list)


@dataclass
class MapUpdate(DataClassJSONMixin):
    rows: int
    cols: int
    tiles: List[Tile]
    metadata: MapMetadata = field(default_factory=MapMetadata)
    props: List[Prop] = None

    def get_edge_between(self, hecs_a: HecsCoord, hecs_b: HecsCoord):
        """Returns the edge between the two given HECS coordinates.

        Assumes they are adjacent, else undefined behavior.

        Returns true if there is an edge (obstacle) between the two coordinates.
        """
        tile_a = self.tile_at(hecs_a)
        tile_b = self.tile_at(hecs_b)
        # If either tile is off-map, return that there is an edge.
        if tile_a is None or tile_b is None:
            logger.info(f"NONE: {tile_a} {tile_b}")
            return True
        bound_a = tile_a.cell.boundary
        bound_b = tile_b.cell.boundary
        return bound_a.get_edge_between(hecs_a, hecs_b) or bound_b.get_edge_between(
            hecs_b, hecs_a
        )

    def tile_at(self, r, c):
        """Returns the tile at the given row and column."""
        location = HecsCoord.from_offset(r, c)
        self.tile_at(location)

    def tile_at(self, hecs: HecsCoord):
        self._refresh_tile_cache(hecs)
        if hecs not in self._tile_cache:
            return None
        return self._tile_cache[hecs]

    def _refresh_tile_cache(self, hecs: HecsCoord):
        if hasattr(self, "_tile_cache"):
            if hecs in self._tile_cache:
                return  # Cache up to date.
            return
        self._tile_cache = {}
        for tile in self.tiles:
            self._tile_cache[tile.cell.coord] = tile
