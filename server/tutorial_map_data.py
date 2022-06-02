from card import Card, Shape, Color
from hex import HecsCoord
from map_utils import *
from messages.map_update import MapMetadata

MAP_WIDTH = 10
MAP_HEIGHT = 10

CARDS = [Card(id=0, location=HecsCoord(a=1, r=3, c=4),
    rotation_degrees=0, shape=Shape.PLUS, color=Color.RED, count=1,
    selected=0), Card(id=1, location=HecsCoord(a=1, r=2, c=6),
    rotation_degrees=0,
    shape=Shape.DIAMOND, color=Color.PINK, count=1, selected=0),
    Card(id=2, location=HecsCoord(a=1, r=0, c=6), rotation_degrees=0,
    shape=Shape.TORUS, color=Color.PINK, count=1, selected=0), Card(id=3,
    location=HecsCoord(a=1, r=2, c=1), rotation_degrees=0, shape=Shape.TRIANGLE
    , color=Color.PINK, count=3, selected=0), Card(id=4,
    location=HecsCoord(a=0, r=1, c=3), rotation_degrees=0, shape=Shape.STAR,
    color=Color.ORANGE, count=1, selected=0), Card(id=5,
    location=HecsCoord(a=1, r=3, c=9), rotation_degrees=0, shape=Shape.TRIANGLE, color=Color.RED, count=2, selected=0), Card(id=6,
    location=HecsCoord(a=0, r=2, c=0), rotation_degrees=0, shape=Shape.SQUARE,
    color=Color.GREEN, count=1, selected=0), Card(id=7, location=HecsCoord(a=0,
    r=1, c=5), rotation_degrees=0, shape=Shape.DIAMOND, color=Color.PINK,
    count=1, selected=0), Card(id=8, location=HecsCoord(a=1, r=2, c=9),
    rotation_degrees=0, shape=Shape.DIAMOND, color=Color.PINK, count=2,
    selected=0), Card(id=9, location=HecsCoord(a=0, r=3, c=2), rotation_degrees=0,
    shape=Shape.DIAMOND, color=Color.BLUE, count=3, selected=0),
    Card(id=10, location=HecsCoord(a=1, r=1, c=3), rotation_degrees=0,
    shape=Shape.PLUS, color=Color.BLUE, count=2, selected=0), Card(id=11,
    location=HecsCoord(a=1, r=0, c=1), rotation_degrees=0, shape=Shape.DIAMOND,
    color=Color.BLACK, count=2, selected=0), Card(id=12,
    location=HecsCoord(a=1, r=4, c=8), rotation_degrees=0, shape=Shape.SQUARE,
    color=Color.YELLOW, count=1, selected=0), Card(id=13,
    location=HecsCoord(a=0, r=2, c=2), rotation_degrees=0, shape=Shape.TRIANGLE
    , color=Color.PINK, count=2, selected=0), Card(id=14,
    location=HecsCoord(a=1, r=4, c=6), rotation_degrees=0, shape=Shape.DIAMOND,
    color=Color.GREEN, count=1, selected=0), Card(id=15,
    location=HecsCoord(a=0, r=3, c=6), rotation_degrees=0, shape=Shape.DIAMOND,
    color=Color.ORANGE, count=3, selected=0), Card(id=16,
    location=HecsCoord(a=1, r=4, c=0), rotation_degrees=0, shape=Shape.TORUS,
    color=Color.BLACK, count=1, selected=0), Card(id=17,
    location=HecsCoord(a=0, r=2, c=6), rotation_degrees=0, shape=Shape.TRIANGLE
    , color=Color.PINK, count=1, selected=0), Card(id=18,
    location=HecsCoord(a=0, r=0, c=6), rotation_degrees=0, shape=Shape.SQUARE,
    color=Color.BLACK, count=1, selected=0), Card(id=19,
    location=HecsCoord(a=0, r=1, c=7), rotation_degrees=0, shape=Shape.PLUS,
    color=Color.BLACK, count=2, selected=0), Card(id=20,
    location=HecsCoord(a=0, r=0, c=3), rotation_degrees=0, shape=Shape.SQUARE,
    color=Color.YELLOW, count=3, selected=0)]

def HardcodedMap():
    """ Hardcoded map of Tile objects, each with HECS coordinates and locations."""
    map = []
    for r in range(0, MAP_HEIGHT):
        row = []
        for c in range(0, MAP_WIDTH):
            tile = GroundTile()
            row.append(tile)
        map.append(row)

    #Pathway around some water at the start.
    map[0][0] = PathTile()
    map[0][1] = PathTile()
    map[0][2] = PathTile()
    map[0][3] = PathTile()
    map[0][4] = PathTile()
    map[0][5] = PathTile()
    map[0][6] = PathTile()
    map[1][0] = PathTile()
    map[1][1] = PathTile()
    map[1][2] = WaterTile()
    map[1][3] = WaterTile()
    map[1][4] = WaterTile()
    map[1][5] = WaterTile()
    map[1][6] = PathTile()

    # Single ramp at start
    map[2][2] = RampToMountain()
    map[2][3] = MountainTile()
    map[2][4] = MountainTile()
    map[2][5] = MountainTile()
    map[2][6] = RampToMountain(180)
    map[3][5] = RampToMountain(240)

    # Add trees
    map[5][5] = GroundTileTrees()
    map[5][7] = GroundTileTrees(60)
    map[6][5] = GroundTileTrees(120)
    map[6][7] = GroundTileTrees(180)

    # Add rocks
    map[4][4] = GroundTileRocky(60)
    map[4][8] = GroundTileRocky(180)
    map[2][9] = GroundTileRocky(240)
    map[5][8] = GroundTileRocky(300)
    map[6][4] = GroundTileRocky()

    # Add a house.
    map[7][7] = GroundTileHouse()

    # Add mountains.
    map[8][5] = MountainTile()
    map[8][6] = MountainTile()
    map[8][7] = MountainTile()
    map[8][8] = MountainTile()
    map[9][5] = MountainTile()
    map[9][6] = MountainTile()
    map[9][7] = RampToMountain(180)

    # Add a street light.
    map[5][3] = GroundTileStreetLight()

    # Add ramps to mountain.
    map[8][4] = RampToMountain()
    map[9][4] = RampToMountain()

    # Fix all the tile coordinates.
    for r in range(0, MAP_HEIGHT):
        for c in range(0, MAP_WIDTH):
            map[r][c].cell.coord = HecsCoord.from_offset(r, c)

    # Flatten the 2D map of tiles to a list.
    map_tiles = [tile for row in map for tile in row]

    # Recompute heights.
    for i in range(len(map_tiles)):
        map_tiles[i].cell.height = LayerToHeight(map_tiles[i].cell.layer)

    return MapUpdate(MAP_HEIGHT, MAP_WIDTH, map_tiles, [], MapMetadata())
