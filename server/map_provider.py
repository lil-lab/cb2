""" This utility streams a hardcoded map to clients. """
from messages.map_update import MapUpdate,Tile
from assets import AssetId
from hex import HecsCoord,HexCell,HexBoundary

def HardcodedMap():
    """ Creates a 10x10 map of Tile objects, each with HECS coordinates and locations."""
    map = []
    for r in range(0,10):
        row = []
        for c in range(0,10):
            tile = GroundTile(r, c)
            row.append(tile)
        map.append(row)

    # Single ramp at start
    map[2][2] = RampToMountain(2,2)

    # Add trees
    map[5][5] = GroundTileTrees(5,5)
    map[5][7] = GroundTileTrees(5,7)
    map[6][5] = GroundTileTrees(6,5)
    map[6][7] = GroundTileTrees(6,7)

    # Add rocks
    map[4][4] = GroundTileRocky(4,4)
    map[2][5] = GroundTileRocky(2,5)
    map[2][7] = GroundTileRocky(2,7)
    map[4][8] = GroundTileRocky(4,8)
    map[2][9] = GroundTileRocky(2,9)
    map[5][8] = GroundTileRocky(5,8)
    map[6][4] = GroundTileRocky(6,4)

    # Add a house.
    map[7][7] = GroundTileHouse(7,7)

    # Add mountains.
    map[8][5] = MountainTile(8,5)
    map[8][6] = MountainTile(8,6)
    map[8][7] = MountainTile(8,7)
    map[8][8] = MountainTile(8,8)
    map[8][9] = MountainTile(8,9)
    map[9][5] = MountainTile(9,5)
    map[9][6] = MountainTile(9,6)
    map[9][7] = MountainTile(9,7)
    map[9][8] = MountainTile(9,8)

    # Add a street light.
    map[5][3] = GroundTileStreetLight(5,3)

    # Add ramps to mountain.
    map[8][4] = RampToMountain(8,4)
    map[9][4] = RampToMountain(9,4)

    # Flatten the 2D map of tiles to a list.
    map_tiles = [tile for row in map for tile in row]

    return MapUpdate(10, 10, map_tiles)

def GroundTile(r, c):
    """ Creates a single tile of ground."""
    return Tile(
        AssetId.GROUND_TILE,
        HexCell(HecsCoord.from_offset(r,c), HexBoundary(0),
            0, # Height (float)
            0,  # Z-Layer (int)
        ),
        0 # Rotation, degrees.
    )

def GroundTileRocky(r, c):
    """ Creates a single tile of rocky ground."""
    return Tile(
        AssetId.GROUND_TILE_ROCKY,
        HexCell(HecsCoord.from_offset(r,c), HexBoundary(0x3F),
            0, # Height (float)
            0  # Z-Layer (int)
        ),
        0 # Rotation, degrees.
    )

def GroundTileStones(r, c):
    """ Creates a single tile of ground with stones."""
    return Tile(
        AssetId.GROUND_TILE_STONES,
        HexCell(HecsCoord.from_offset(r,c), HexBoundary(0x3F),
            0, # Height (float)
            0  # Z-Layer (int)
        ),
        0 # Rotation, degrees.
    )

def GroundTileTrees(r, c):
    """ Creates a single tile of ground with several trees. """
    return Tile(
        AssetId.GROUND_TILE_TREES,
        HexCell(HecsCoord.from_offset(r,c), HexBoundary(0x3F),
            0, # Height (float)
            0  # Z-Layer (int)
        ),
        0 # Rotation, degrees.
    )

def GroundTileSingleTree(r, c):
    """ Creates a single tile of ground with a tree."""
    return Tile(
        AssetId.GROUND_TILE_TREES_2,
        HexCell(HecsCoord.from_offset(r,c), HexBoundary(0x3F),
            0, # Height (float)
            0  # Z-Layer (int)
        ),
        0 # Rotation, degrees.
    )
    
def GroundTileForest(r, c):
    """ Creates a single tile of ground with a forest."""
    return Tile(
        AssetId.GROUND_TILE_FOREST,
        HexCell(HecsCoord.from_offset(r,c), HexBoundary(0x3F),
            0, # Height (float)
            0  # Z-Layer (int)
        ),
        0 # Rotation, degrees.
    ) 

def GroundTileHouse(r, c):
    """ Creates a single tile of ground with a house."""
    return Tile(
        AssetId.GROUND_TILE_HOUSE,
        HexCell(HecsCoord.from_offset(r,c), HexBoundary(0x3F),
            0, # Height (float)
            0  # Z-Layer (int)
        ),
        0 # Rotation, degrees.
    )
    
def GroundTileStreetLight(r, c):
    """ Creates a single tile of ground with a street light."""
    return Tile(
        AssetId.GROUND_TILE_STREETLIGHT,
        HexCell(HecsCoord.from_offset(r,c), HexBoundary(0x3F),
            0, # Height (float)
            0  # Z-Layer (int)
        ),
        0 # Rotation, degrees.
    )

def MountainTile(r, c):
    """ Creates a single tile of mountain."""
    return Tile(
        AssetId.MOUNTAIN_TILE,
        HexCell(HecsCoord.from_offset(r,c), HexBoundary(0),
            0.325, # Height (float)
            2  # Z-Layer (int)
        ),
        0 # Rotation, degrees.
    )

def RampToMountain(r, c):
    """ Creates a single tile of ramp."""
    return Tile(
        AssetId.RAMP_TO_MOUNTAIN,
        HexCell(HecsCoord.from_offset(r,c), HexBoundary(0b101101),
            0.275, # Height (float)
            1  # Z-Layer (int)
        ),
        0 # Rotation, degrees.
    )

class HardcodedMapProvider(object):
    def __init__(self):
        map = HardcodedMap()
        self._tiles = map.tiles
        self._rows = map.rows
        self._cols = map.cols
        self.add_map_boundaries()
        self.add_layer_boundaries()
    
    def add_map_boundaries(self):
        """ Adds boundaries to the hex map edges. """
        for i,t in enumerate(self._tiles):
            loc = t.cell.coord
            for n in loc.neighbors():
                (nr, nc) = n.to_offset_coordinates()
                # If the neighbor cell is outside the map, add an edge to this cell's boundary.
                if not (0 <= nr < self._rows and 0 <= nc < self._cols):
                    self._tiles[i].cell.boundary.set_edge_between(loc, n)
    
    def add_layer_boundaries(self):
        """ If two neighboring cells differ in Z-layer, adds an edge between them. """
        for i,it in enumerate(self._tiles):
            iloc = it.cell.coord
            for j,jt in enumerate(self._tiles):
                jloc = jt.cell.coord
                if (iloc.equals(jloc)):
                    continue
                if not (iloc.is_adjacent_to(jloc)):
                    continue
                if abs(it.cell.layer - jt.cell.layer) > 1:
                    self._tiles[i].cell.boundary.set_edge_between(iloc, jloc)
    
    def get_map(self):
        return MapUpdate(self._rows, self._cols, self._tiles)