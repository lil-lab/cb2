""" This utility streams a hardcoded map to clients. """
from assets import AssetId
from card import Card, Shape, Color
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from enum import Enum
from hex import HecsCoord, HexCell, HexBoundary
from messages.map_update import MapUpdate, Tile
from queue import Queue

import itertools
import logging
import random
import numpy as np

MAP_WIDTH = 16
MAP_HEIGHT = 16

logger = logging.getLogger()

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

    return MapUpdate(MAP_HEIGHT, MAP_WIDTH, map_tiles, [])


@dataclass_json
@dataclass
class City:
    r: int
    c: int
    size: int

# A point in a BFS or DFS search from a certain origin.
@dataclass_json
@dataclass
class SearchPoint:
    r: int
    c: int
    radius: int

def place_city(map, city):
    """ Places a city on the map."""
    # Place the center path tile.
    map[city.r][city.c] = PathTile()

    # Place two cross streets going through city.
    for i in range(city.size + 2):
        if city.c + i < MAP_WIDTH:
            r,c = (city.r, city.c + i)
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                map[r][c] = PathTile()
        if city.r + i < MAP_HEIGHT:
            r,c = (city.r + i, city.c)
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                map[r][c] = PathTile()
        if city.c - i >= 0: 
            r,c = (city.r, city.c - i)
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                map[r][c] = PathTile()
        if city.r - i >= 0:
            r,c = (city.r - i, city.c)
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                map[r][c] = PathTile()

    point_queue = Queue()
    point_queue.put(SearchPoint(city.r, city.c, 0))
    covered_points = set()
    while not point_queue.empty():
        point = point_queue.get()
        covered_points.add((point.r, point.c))
        hc = HecsCoord.from_offset(point.r, point.c)
        for neighbor in hc.neighbors():
            r,c = neighbor.to_offset_coordinates()
            if (r, c) in covered_points:
                continue
            if r < 0 or r >= MAP_HEIGHT or c < 0 or c >= MAP_WIDTH:
                continue
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                if point.radius % 3 == 0:
                    tile_generator = np.random.choice([GroundTile, GroundTileTrees, GroundTileStreetLight], size=1, p=[0.6, 0.2, 0.2])[0]
                    map[r][c] = tile_generator(rotation_degrees = random.choice([0, 60, 120, 180, 240, 300]))
                elif point.radius % 3 == 1:
                    map[r][c] = PathTile()
                elif point.radius % 3 == 2:
                    coord = HecsCoord.from_offset(r, c)
                    center = HecsCoord.from_offset(city.r, city.c)
                    degrees_to_center = coord.degrees_to(center)
                    map[r][c] = GroundTileHouse(rotation_degrees=degrees_to_center)
            if point.radius < city.size:
                point_queue.put(SearchPoint(r, c, point.radius + 1))

@dataclass_json
@dataclass
class Lake:
    r: int
    c: int
    size: int

def place_lake(map, lake):
    """ Places a lake on the map."""
    # Place the center tile.
    map[lake.r][lake.c] = WaterTile()

    # Place two cross streets going through city.
    for i in range(lake.size, lake.size + 2):
        if lake.c + i < MAP_WIDTH:
            r,c = (lake.r, lake.c + i)
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                map[r][c] = PathTile()
        if lake.r + i < MAP_HEIGHT:
            r,c = (lake.r + i, lake.c)
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                map[r][c] = PathTile()
        if lake.c - i >= 0: 
            r,c = (lake.r, lake.c - i)
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                map[r][c] = PathTile()
        if lake.r - i >= 0:
            r,c = (lake.r - i, lake.c)
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                map[r][c] = PathTile()

    point_queue = Queue()
    point_queue.put(SearchPoint(lake.r, lake.c, 0))
    covered_points = set()
    while not point_queue.empty():
        point = point_queue.get()
        covered_points.add((point.r, point.c))
        hc = HecsCoord.from_offset(point.r, point.c)
        for neighbor in hc.neighbors():
            r,c = neighbor.to_offset_coordinates()
            if (r, c) in covered_points:
                continue
            # Keep lakes away from the edge of the map.
            if r < 2 or r >= MAP_HEIGHT - 2 or c < 2 or c >= MAP_WIDTH - 2:
                continue
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                if point.radius == lake.size:
                    tile_generator = np.random.choice([GroundTile, GroundTileTrees, GroundTileStreetLight], size=1, p=[0.6, 0.2, 0.2])[0]
                    map[r][c] = tile_generator(rotation_degrees = random.choice([0, 60, 120, 180, 240, 300]))
                elif point.radius == lake.size - 1:
                    map[r][c] = PathTile()
                else:
                    map[r][c] = WaterTile()
            if point.radius < lake.size:
                point_queue.put(SearchPoint(r, c, point.radius + 1))

class MountainType(Enum):
    NONE = 0
    SMALL = 1
    MEDIUM = 2
    LARGE = 3

@dataclass_json
@dataclass
class Mountain:
    r: int
    c: int
    type: MountainType

def offset_coord_in_map(map, offset):
    return (offset[0] in range(1, len(map) - 1) and
            offset[1] in range(1, len(map[offset[0]]) - 1))

def place_small_mountain(map, mountain):
    mountain_coords = []
    # MountainTile(rotation_degrees=0)
    # RampToMountain(rotation_degrees=0)
    map[mountain.r][mountain.c] = MountainTile(rotation_degrees=0)
    start = HecsCoord.from_offset(mountain.r, mountain.c)
    mountain_coords.append(start)
    mountain_coords.append(start.right())
    mountain_coords.append(start.down_left())
    mountain_coords.append(start.down_right())

    for coord in mountain_coords:
        offset = coord.to_offset_coordinates()
        if offset_coord_in_map(map, offset):
            map[offset[0]][offset[1]] = MountainTile(rotation_degrees=0)

    first_ramp_offset = start.left().to_offset_coordinates()
    second_ramp_offset = start.right().down_right().to_offset_coordinates()
    if offset_coord_in_map(map, first_ramp_offset):
        map[first_ramp_offset[0]][first_ramp_offset[1]] = RampToMountain(rotation_degrees=00)
    if offset_coord_in_map(map, second_ramp_offset):
        map[second_ramp_offset[0]][second_ramp_offset[1]] = RampToMountain(rotation_degrees=180)

def place_medium_mountain(map, mountain):
    mountain_coords = []
    # MountainTile(rotation_degrees=0)
    # RampToMountain(rotation_degrees=0)
    map[mountain.r][mountain.c] = MountainTile(rotation_degrees=0)
    start = HecsCoord.from_offset(mountain.r, mountain.c)
    mountain_coords.append(start)
    mountain_coords.append(start.down_right())
    mountain_coords.append(start.down_left())
    mountain_coords.append(start.down_right().down_right())
    mountain_coords.append(start.down_right().down_left())

    for coord in mountain_coords:
        offset = coord.to_offset_coordinates()
        if offset_coord_in_map(map, offset):
            map[offset[0]][offset[1]] = MountainTile(rotation_degrees=0)

    first_ramp_offset = start.left().to_offset_coordinates()
    second_ramp_offset = start.down_right().down_right().down_left().to_offset_coordinates()
    if offset_coord_in_map(map, first_ramp_offset):
        map[first_ramp_offset[0]][first_ramp_offset[1]] = RampToMountain(rotation_degrees=60)
    if offset_coord_in_map(map, second_ramp_offset):
        map[second_ramp_offset[0]][second_ramp_offset[1]] = RampToMountain(rotation_degrees=240)

def place_large_mountain(map, mountain):
    mountain_coords = []
    # MountainTile(rotation_degrees=0)
    # RampToMountain(rotation_degrees=0)
    map[mountain.r][mountain.c] = MountainTile(rotation_degrees=0)
    start = HecsCoord.from_offset(mountain.r, mountain.c)
    mountain_coords.append(start)
    for coord in start.neighbors():
        mountain_coords.append(coord)

    for coord in mountain_coords:
        offset = coord.to_offset_coordinates()
        if offset_coord_in_map(map, offset):
            map[offset[0]][offset[1]] = MountainTile(rotation_degrees=0)

    first_ramp_offset = start.left().left().to_offset_coordinates()
    second_ramp_offset = start.right().right().to_offset_coordinates()
    if offset_coord_in_map(map, first_ramp_offset):
        map[first_ramp_offset[0]][first_ramp_offset[1]] = RampToMountain(rotation_degrees=0)
    if offset_coord_in_map(map, second_ramp_offset):
        map[second_ramp_offset[0]][second_ramp_offset[1]] = RampToMountain(rotation_degrees=180)

def place_mountain(map, mountain):
    if mountain.type == MountainType.SMALL:
        place_small_mountain(map, mountain)
    elif mountain.type == MountainType.MEDIUM:
        place_medium_mountain(map, mountain)
    elif mountain.type == MountainType.LARGE:
        place_large_mountain(map, mountain)
    else:
        logger.error(f"Unknown mountain type: {mountain.type}")
    
def RandomMap():
    """ Random map of Tile objects, each with HECS coordinates and locations."""
    map = []
    for r in range(0, MAP_HEIGHT):
        row = []
        for c in range(0, MAP_WIDTH):
            tile = EmptyTile()
            row.append(tile)
        map.append(row)
    
    # Generate candidates for feature centers.
    rows = list(range(1, MAP_HEIGHT - 2, 6))
    cols = list(range(1, MAP_WIDTH - 2, 6))
    feature_center_candidates = list(itertools.product(rows, cols))
    logger.info(f"Feature points: {len(feature_center_candidates)}")
    random.shuffle(feature_center_candidates)

    # Add a random number of mountains.
    number_of_mountains = min(random.randint(1, 4), len(feature_center_candidates))
    mountain_centers = feature_center_candidates[0:number_of_mountains]
    feature_center_candidates = feature_center_candidates[number_of_mountains:len(feature_center_candidates)]
    logger.info(f"Remaining feature points: {len(feature_center_candidates)}")

    mountains = [Mountain(r, c, random.choice([MountainType.SMALL, MountainType.MEDIUM, MountainType.LARGE])) for r, c in mountain_centers]
    for mountain in mountains:
        place_mountain(map, mountain)

    # Add a random number of lakes
    number_of_lakes = min(random.randint(2, 3), len(feature_center_candidates))
    logger.info(f"Number of lakes: {number_of_lakes}")
    lake_centers = feature_center_candidates[0:number_of_lakes]
    feature_center_candidates = feature_center_candidates[number_of_lakes:len(feature_center_candidates)]
    logger.info(f"Remaining feature points: {len(feature_center_candidates)}")
        
    lakes = [Lake(r, c, random.randint(2, 4)) for r, c in lake_centers] 
    for lake in lakes:
        place_lake(map, lake)

    # Add a random number of cities.
    number_of_cities = min(random.randint(2, 4), len(feature_center_candidates))
    logger.info(f"Number of cities: {number_of_cities}")
    city_centers = feature_center_candidates[0:number_of_cities]
    feature_center_candidates = feature_center_candidates[number_of_cities:len(feature_center_candidates)]
    logger.info(f"Remaining feature points: {len(feature_center_candidates)}")

    cities = [City(r, c, random.randint(3, 4)) for r, c in city_centers]
    for city in cities:
        place_city(map, city)

    # Fix all the tile coordinates and replace empty tiles with ground tiles.
    for r in range(0, MAP_HEIGHT):
        for c in range(0, MAP_WIDTH):
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                map[r][c] = GroundTile()
            map[r][c].cell.coord = HecsCoord.from_offset(r, c)

    # Flatten the 2D map of tiles to a list.
    map_tiles = [tile for row in map for tile in row]

    # Recompute heights.
    for i in range(len(map_tiles)):
        map_tiles[i].cell.height = LayerToHeight(map_tiles[i].cell.layer)
    


    return MapUpdate(MAP_HEIGHT, MAP_WIDTH, map_tiles, [])

class CardGenerator(object):
    def __init__(self, id_assigner):
        self._id_assigner = id_assigner

    def generate_card_at(self, r, c, shape, color, count):
        return Card(self._id_assigner.alloc(),
                    HecsCoord.from_offset(r, c),
                    0,
                    shape,
                    color,
                    count,
                    0)

    def generate_random_card_at(self, r, c):
        return Card(self._id_assigner.alloc(),
                    HecsCoord.from_offset(r, c),
                    0,
                    self.random_shape(),
                    self.random_color(),
                    self.random_count(),
                    0)

    def random_shape(self):
        shapes = [Shape.PLUS, Shape.TORUS, Shape.HEART, Shape.DIAMOND,
                  Shape.SQUARE, Shape.STAR, Shape.TRIANGLE]
        return random.choice(shapes)

    def random_color(self):
        colors = [Color.BLACK, Color.BLUE, Color.GREEN, Color.ORANGE,
                  Color.PINK, Color.RED, Color.YELLOW]
        return random.choice(colors)

    def random_count(self):
        return random.randint(1, 3)


def LayerToHeight(layer):
    """ Converts a layer to a height."""
    layer_to_height = {
        0: 0.05,
        1: 0.275,
        2: 0.355,
    }
    if layer not in layer_to_height:
        return layer_to_height[0]

    return layer_to_height[layer]

def EmptyTile():
    return Tile(AssetId.EMPTY_TILE,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0),
                LayerToHeight(0),  # Height (float)
                0,  # Z-Layer (int)
                ),
        0
    )

def GroundTile(rotation_degrees=0):
    """ Creates a single tile of ground."""
    return Tile(
        AssetId.GROUND_TILE,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0),
                LayerToHeight(0),  # Height (float)
                0,  # Z-Layer (int)
                ),
        rotation_degrees
    )


def WaterTile(rotation_degrees=0):
    """ Creates a single tile of Water."""
    return Tile(
        AssetId.WATER_TILE,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0,  # Z-Layer (int)
                ),
        rotation_degrees
    )


def PathTile(rotation_degrees=0):
    """ Creates a single tile of Path."""
    return Tile(
        AssetId.GROUND_TILE_PATH,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0),
                LayerToHeight(0),  # Height (float)
                0,  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileRocky(rotation_degrees=0):
    """ Creates a single tile of rocky ground."""
    return Tile(
        AssetId.GROUND_TILE_ROCKY,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileStones(rotation_degrees=0):
    """ Creates a single tile of ground with stones."""
    return Tile(
        AssetId.GROUND_TILE_STONES,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileTrees(rotation_degrees=0):
    """ Creates a single tile of ground with several trees. """
    return Tile(
        AssetId.GROUND_TILE_TREES,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileSingleTree(rotation_degrees=0):
    """ Creates a single tile of ground with a tree."""
    return Tile(
        AssetId.GROUND_TILE_TREES_2,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileForest(rotation_degrees=0):
    """ Creates a single tile of ground with a forest."""
    return Tile(
        AssetId.GROUND_TILE_FOREST,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileHouse(rotation_degrees=0):
    """ Creates a single tile of ground with a house."""
    return Tile(
        AssetId.GROUND_TILE_HOUSE,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileStreetLight(rotation_degrees=0):
    """ Creates a single tile of ground with a street light."""
    return Tile(
        AssetId.GROUND_TILE_STREETLIGHT,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def MountainTile(rotation_degrees=0):
    """ Creates a single tile of mountain."""
    return Tile(
        AssetId.MOUNTAIN_TILE,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary(0),
                LayerToHeight(2),  # Height (float)
                2  # Z-Layer (int)
                ),
        rotation_degrees
    )


def RampToMountain(rotation_degrees=0):
    """ Creates a single tile of ramp."""
    return Tile(
        AssetId.RAMP_TO_MOUNTAIN,
        HexCell(HecsCoord.from_offset(0, 0), HexBoundary.rotate_cw(HexBoundary(0b101101), rotation_degrees),
                LayerToHeight(1),  # Height (float)
                1  # Z-Layer (int)
                ),
        rotation_degrees
    )

class MapType(Enum):
    NONE = 0
    RANDOM = 1
    HARDCODED = 2

class MapProvider(object):
    def __init__(self, map_type, id_assigner):
        map = None
        if map_type == MapType.RANDOM:
            map = RandomMap()
        elif map_type == MapType.HARDCODED:
            map = HardcodedMap()
        else:
            raise ValueError("Invalid map type NONE specified.")
        
        self._tiles = map.tiles
        self._rows = map.rows
        self._cols = map.cols
        self._cards = []
        self._selected_cards = {}
        self._card_generator = CardGenerator(id_assigner)
        potential_spawn_tiles = [tile for tile in self._tiles if tile.asset_id in [AssetId.GROUND_TILE, AssetId.GROUND_TILE_PATH, AssetId.MOUNTAIN_TILE]]
        card_spawn_weights = [self.calculate_card_spawn_weight(tile) for tile in potential_spawn_tiles]
        card_spawn_weights = [float(weight) / sum(card_spawn_weights) for weight in card_spawn_weights]
        number_of_tiles = len(potential_spawn_tiles)
        number_of_cards = random.randint(int(number_of_tiles * 0.2), int(number_of_tiles * 0.4))
        card_spawn_tiles = np.random.choice(potential_spawn_tiles, size=number_of_cards, replace=False, p=card_spawn_weights)

        for tile in card_spawn_tiles:
            (r, c) = tile.cell.coord.to_offset_coordinates()
            self._cards.append(self._card_generator.generate_random_card_at(r, c))

        # Index cards generated.
        self._cards_by_location = {}
        for card in self._cards:
            self._cards_by_location[card.location] = card
        self.add_map_boundaries()
        self.add_layer_boundaries()
        self._spawn_points = [tile.cell.coord for tile in self._tiles
                              if (tile.asset_id == AssetId.GROUND_TILE_PATH) and (tile.cell.coord not in self._cards_by_location)]
    
    def calculate_card_spawn_weight(self, tile):
        if tile.asset_id == AssetId.GROUND_TILE:
            return 1
        elif tile.asset_id == AssetId.GROUND_TILE_PATH:
            return 2
        elif tile.asset_id == AssetId.MOUNTAIN_TILE:
            return 2
        else:
            return 0

    def add_map_boundaries(self):
        """ Adds boundaries to the hex map edges. """
        for i, t in enumerate(self._tiles):
            loc = t.cell.coord
            for n in loc.neighbors():
                (nr, nc) = n.to_offset_coordinates()
                # If the neighbor cell is outside the map, add an edge to this cell's boundary.
                if not (0 <= nr < self._rows and 0 <= nc < self._cols):
                    self._tiles[i].cell.boundary.set_edge_between(loc, n)

    def add_layer_boundaries(self):
        """ If two neighboring cells differ in Z-layer, adds an edge between them. """
        for i, it in enumerate(self._tiles):
            iloc = it.cell.coord
            for j, jt in enumerate(self._tiles):
                jloc = jt.cell.coord
                if (iloc.equals(jloc)):
                    continue
                if not (iloc.is_adjacent_to(jloc)):
                    continue
                if abs(it.cell.layer - jt.cell.layer) > 1:
                    self._tiles[i].cell.boundary.set_edge_between(iloc, jloc)

    def get_cards(self):
        return self._cards

    def set_selected(self, card_id, selected):
        for idx, card in enumerate(self._cards):
            if card.id == card_id:
                self._cards[idx].selected = selected
                if selected:
                    card.selected = True
                    self._selected_cards[card_id] = card
                else:
                    del self._selected_cards[card_id]
                break
    
    def spawn_points(self):
        return self._spawn_points

    def selected_cards(self):
        return self._selected_cards.values()

    def card_by_location(self, location):
        return self._cards_by_location.get(location, None)

    def map(self):
        return MapUpdate(self._rows, self._cols, self._tiles, [card.prop() for card in self._cards])
