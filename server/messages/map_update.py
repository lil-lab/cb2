from server.hex import HexCell, HecsCoord

from mashumaro.mixins.json import DataClassJSONMixin
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from enum import Enum
from marshmallow import fields
from typing import List

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
    """ The type of lake to generate."""
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

@dataclass(frozen=True)
class MapUpdate(DataClassJSONMixin):
    rows: int
    cols: int
    tiles: List[Tile]
    metadata: MapMetadata = field(default_factory=MapMetadata)
