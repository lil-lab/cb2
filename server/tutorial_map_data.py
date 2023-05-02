from server.card import Card, Color, Shape
from server.hex import HecsCoord
from server.map_utils import (
    GroundTile,
    GroundTileHouse,
    GroundTileRocky,
    GroundTileStreetLightFoilage,
    GroundTileTree,
    GroundTileTreeRocks,
    GroundTileTrees,
    HouseType,
    LayerToHeight,
    MountainTile,
    MountainTileTree,
    PathTile,
    RampToMountain,
    WaterTile,
)
from server.messages.map_update import MapMetadata, MapUpdate

MAP_WIDTH = 10
MAP_HEIGHT = 10

CARDS = [
    Card(
        id=0,
        location=HecsCoord(a=1, r=3, c=3),
        rotation_degrees=0,
        shape=Shape.PLUS,
        color=Color.RED,
        count=1,
        selected=0,
    ),
    Card(
        id=1,
        location=HecsCoord(a=1, r=2, c=6),
        rotation_degrees=0,
        shape=Shape.DIAMOND,
        color=Color.PINK,
        count=1,
        selected=0,
    ),
    Card(
        id=3,
        location=HecsCoord(a=1, r=2, c=1),
        rotation_degrees=0,
        shape=Shape.TRIANGLE,
        color=Color.PINK,
        count=3,
        selected=0,
    ),
    Card(
        id=4,
        location=HecsCoord(a=0, r=1, c=4),
        rotation_degrees=0,
        shape=Shape.STAR,
        color=Color.ORANGE,
        count=1,
        selected=0,
    ),
    Card(
        id=5,
        location=HecsCoord(a=1, r=3, c=9),
        rotation_degrees=0,
        shape=Shape.TRIANGLE,
        color=Color.RED,
        count=2,
        selected=0,
    ),
    Card(
        id=6,
        location=HecsCoord(a=0, r=2, c=0),
        rotation_degrees=0,
        shape=Shape.SQUARE,
        color=Color.GREEN,
        count=1,
        selected=0,
    ),
    Card(
        id=8,
        location=HecsCoord(a=1, r=2, c=9),
        rotation_degrees=0,
        shape=Shape.DIAMOND,
        color=Color.PINK,
        count=2,
        selected=0,
    ),
    Card(
        id=9,
        location=HecsCoord(a=0, r=3, c=2),
        rotation_degrees=0,
        shape=Shape.DIAMOND,
        color=Color.BLUE,
        count=3,
        selected=0,
    ),
    Card(
        id=10,
        location=HecsCoord(a=0, r=2, c=4),
        rotation_degrees=0,
        shape=Shape.PLUS,
        color=Color.BLUE,
        count=2,
        selected=0,
    ),
    Card(
        id=11,
        location=HecsCoord(a=1, r=0, c=1),
        rotation_degrees=0,
        shape=Shape.DIAMOND,
        color=Color.BLACK,
        count=2,
        selected=0,
    ),
    Card(
        id=12,
        location=HecsCoord(a=1, r=4, c=8),
        rotation_degrees=0,
        shape=Shape.SQUARE,
        color=Color.YELLOW,
        count=1,
        selected=0,
    ),
    Card(
        id=13,
        location=HecsCoord(a=0, r=2, c=2),
        rotation_degrees=0,
        shape=Shape.TRIANGLE,
        color=Color.PINK,
        count=2,
        selected=0,
    ),
    Card(
        id=14,
        location=HecsCoord(a=0, r=4, c=6),
        rotation_degrees=0,
        shape=Shape.DIAMOND,
        color=Color.GREEN,
        count=1,
        selected=0,
    ),
    Card(
        id=16,
        location=HecsCoord(a=1, r=4, c=5),
        rotation_degrees=0,
        shape=Shape.TORUS,
        color=Color.BLACK,
        count=1,
        selected=0,
    ),
    Card(
        id=17,
        location=HecsCoord(a=0, r=2, c=6),
        rotation_degrees=0,
        shape=Shape.TRIANGLE,
        color=Color.PINK,
        count=1,
        selected=0,
    ),
]


def HardcodedMap():
    """Hardcoded map of Tile objects, each with HECS coordinates and locations."""
    map = []
    for r in range(0, MAP_HEIGHT):
        row = []
        for c in range(0, MAP_WIDTH):
            tile = GroundTile()
            row.append(tile)
        map.append(row)

    # Houses & Trees around some water at the start.
    map[0][2] = GroundTileHouse(rotation_degrees=120, type=HouseType.HOUSE_PINK)
    map[1][2] = GroundTileHouse(rotation_degrees=120, type=HouseType.HOUSE_ORANGE)
    map[0][3] = GroundTileTreeRocks()
    map[0][4] = GroundTileTree()
    map[1][3] = WaterTile()
    map[1][4] = WaterTile()
    map[0][5] = GroundTileTree()
    map[1][5] = GroundTileTree()

    # Mountain near start
    map[3][2] = RampToMountain()
    map[2][4] = MountainTile()
    map[2][5] = MountainTile()
    map[4][4] = MountainTile()
    map[4][5] = MountainTile()
    map[3][3] = MountainTile()
    map[3][4] = MountainTileTree()
    map[3][5] = MountainTile()
    map[3][6] = RampToMountain(180)

    # Path continues north of mountain to a house.
    map[3][7] = PathTile()
    map[2][8] = PathTile()

    map[1][8] = GroundTileHouse(rotation_degrees=120, type=HouseType.TRIPLE_HOUSE_BLUE)

    # Add trees
    map[5][5] = GroundTileTrees()
    map[5][7] = GroundTileTrees(60)
    map[6][5] = GroundTileTrees(120)
    map[6][7] = GroundTileTrees(180)

    # Add rocks
    map[6][4] = GroundTileRocky()
    map[2][9] = GroundTileRocky()

    # Add a house.
    map[7][7] = GroundTileHouse()

    # Add a snowy mountain.
    map[8][5] = MountainTile(snowy=True)
    map[8][6] = MountainTile(snowy=True)
    map[8][7] = MountainTileTree(snowy=True)
    map[9][5] = MountainTile(snowy=True)
    map[9][6] = MountainTile(snowy=True)
    map[9][7] = RampToMountain(180, snowy=True)
    map[9][4] = RampToMountain(snowy=True)

    # Add some water next to the snow mountain.
    map[7][5] = WaterTile()
    map[7][6] = WaterTile()
    map[6][6] = WaterTile()

    # Path from ramp at [3][2] to snowy ramp at [9][4]
    map[3][1] = PathTile()
    map[4][1] = PathTile()
    map[5][0] = PathTile()
    map[6][1] = PathTile()
    map[7][1] = PathTile()
    map[8][2] = PathTile()
    map[8][3] = PathTile()
    map[9][3] = PathTile()
    map[9][8] = PathTile()
    map[8][8] = PathTile()
    map[4][8] = PathTile()
    map[5][8] = PathTile()
    map[6][8] = PathTile()
    map[7][8] = PathTile()

    # Add a street light.
    map[5][3] = GroundTileStreetLightFoilage()

    # Fix all the tile coordinates.
    for r in range(0, MAP_HEIGHT):
        for c in range(0, MAP_WIDTH):
            map[r][c].cell.coord = HecsCoord.from_offset(r, c)

    # Flatten the 2D map of tiles to a list.
    map_tiles = [tile for row in map for tile in row]

    # Recompute heights.
    for i in range(len(map_tiles)):
        map_tiles[i].cell.height = LayerToHeight(map_tiles[i].cell.layer)

    map_metadata = MapMetadata([], [], [], [], 0)
    return MapUpdate(MAP_HEIGHT, MAP_WIDTH, map_tiles, map_metadata)
