""" This utility streams a hardcoded map to clients. """
from assets import AssetId
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from enum import Enum
from hex import HecsCoord, HexCell, HexBoundary
from map_utils import *
from messages.map_update import MapUpdate, Tile
from queue import Queue

import asyncio
import dataclasses
import itertools
import logging
import math
import random
import card
import numpy as np
import tutorial_map_data

from util import IdAssigner

MAP_WIDTH = 16
MAP_HEIGHT = 16

logger = logging.getLogger()

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
                    degrees_to_center = coord.degrees_to(center) - 60
                    map[r][c] = GroundTileHouse(rotation_degrees=degrees_to_center, type=HouseType.RANDOM)
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

    placed_coords = mountain_coords + [start.left(), start.right().down_right()]
    for coord in placed_coords:
        for neighbor in coord.neighbors():
            offset = neighbor.to_offset_coordinates()
            if offset_coord_in_map(map, offset):
                if map[offset[0]][offset[1]].asset_id == AssetId.EMPTY_TILE:
                    map[offset[0]][offset[1]] = GroundTile()

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

    placed_coords = mountain_coords + [start.left(), start.down_right().down_right().down_left()]
    for coord in placed_coords:
        for neighbor in coord.neighbors():
            offset = neighbor.to_offset_coordinates()
            if offset_coord_in_map(map, offset):
                if map[offset[0]][offset[1]].asset_id == AssetId.EMPTY_TILE:
                    map[offset[0]][offset[1]] = GroundTile()

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

    placed_coords = mountain_coords + [start.left().left(), start.right().right()]
    for coord in placed_coords:
        for neighbor in coord.neighbors():
            offset = neighbor.to_offset_coordinates()
            if offset_coord_in_map(map, offset):
                if map[offset[0]][offset[1]].asset_id == AssetId.EMPTY_TILE:
                    map[offset[0]][offset[1]] = GroundTile()

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
        return card.Card(
            self._id_assigner.alloc(),
            HecsCoord.from_offset(r, c),
            0,
            shape,
            color,
            count,
            0)

    def generate_random_card_at(self, r, c):
        return card.Card(
            self._id_assigner.alloc(),
            HecsCoord.from_offset(r, c),
            0,
            self.random_shape(),
            self.random_color(),
            self.random_count(),
            0)

    def random_shape(self):
        shapes = [
            card.Shape.PLUS,
            card.Shape.TORUS,
            card.Shape.HEART,
            card.Shape.DIAMOND,
            card.Shape.SQUARE,
            card.Shape.STAR,
            card.Shape.TRIANGLE
        ]
        return random.choice(shapes)

    def random_color(self):
        colors = [card.Color.BLACK,
                  card.Color.BLUE,
                  card.Color.GREEN,
                  card.Color.ORANGE,
                  card.Color.PINK,
                  card.Color.RED,
                  card.Color.YELLOW]
        return random.choice(colors)

    def random_count(self):
        return random.randint(1, 3)


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
            map = tutorial_map_data.HardcodedMap()
        else:
            raise ValueError("Invalid map type NONE specified.")
        
        self._tiles = map.tiles
        self._rows = map.rows
        self._cols = map.cols
        self._cards = []
        self._selected_cards = {}
        self._card_generator = CardGenerator(id_assigner)
        self.add_map_boundaries()
        self.add_layer_boundaries()
        if map_type == MapType.HARDCODED:
            self._cards = []
            list(tutorial_map_data.CARDS)
            for tutorial_card in tutorial_map_data.CARDS:
                # This line creates a copy of the hardcoded card. Otherwise
                # state persists between instances (very bad! this took a while
                # to debug)
                card_copy = dataclasses.replace(tutorial_card)
                card_copy.id = id_assigner.alloc()
                self._cards.append(card_copy)
        else: 
            # Sort through the potential spawn tiles via floodfill and find
            # partitions (regions which are blocked off by walls or edges).
            # Then, remove all spaces which aren't in the largest partition as
            # spawn tiles.            
            spaces = FloodFillPartitionTiles(self._tiles)
            sorted_spaces = sorted(spaces, key=len, reverse=True)
            # Only spawn cards in the largest contiguous region.
            logger.info(f"NUMBER OF PARTITIONS: {len(sorted_spaces)}")
            self._potential_spawn_tiles = sorted_spaces[0]

            self._potential_spawn_tiles = [tile 
                                        for tile in self._potential_spawn_tiles
                                        if tile.asset_id in [AssetId.GROUND_TILE, AssetId.GROUND_TILE_PATH, AssetId.MOUNTAIN_TILE]]

            number_of_cards = 21
            number_of_sets = math.ceil(number_of_cards / 3)
            card_spawn_locations = self.choose_card_spawn_locations(number_of_sets * 3)

            for _ in range(number_of_sets):
                card_configs = card.RandomUniqueSet()
                for config in card_configs:
                    (r, c) = card_spawn_locations.pop()
                    (shape, color, count) = config
                    self._cards.append(self._card_generator.generate_card_at(r, c, shape, color, count))

        # Index cards generated.
        self._cards_by_location = {}
        for generated_card in self._cards:
            self._cards_by_location[generated_card.location] = generated_card
        self._spawn_points = [tile.cell.coord for tile in self._tiles
                              if (tile.asset_id == AssetId.GROUND_TILE_PATH) and (tile.cell.coord not in self._cards_by_location)]

    def choose_card_spawn_locations(self, n):
        """ Returns a list of size n of spawn locations for cards. Does not return a location that is actively occupied by an existing card."""
        card_spawn_weights = [self.calculate_card_spawn_weight(tile) for tile in self._potential_spawn_tiles]
        
        # Prevents double-placing of a card (spawning a card on top of an existing card)
        # Yes this is computationally slower than it could be (O(n) instead of ammortized O(c)), but this doesn't happen often.
        card_locations = set([card.location.to_offset_coordinates() for card in self._cards])
        for i, tile_weight in enumerate(zip(self._potential_spawn_tiles, card_spawn_weights)):
            if tile_weight[0].cell.coord.to_offset_coordinates() in card_locations:
                card_spawn_weights[i] = 0
        
        # Normalize card spawn weights so that they sum to 1.
        card_spawn_weights = [float(weight) / sum(card_spawn_weights) for weight in card_spawn_weights]

        spawn_tiles = np.random.choice(self._potential_spawn_tiles, size=n, replace=False, p=card_spawn_weights)
        return [tile.cell.coord.to_offset_coordinates() for tile in spawn_tiles]
    
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
        loc_to_tile_index = {}
        for i, it in enumerate(self._tiles):
            iloc = it.cell.coord
            loc_to_tile_index[iloc] = i
        for i, it in enumerate(self._tiles):
            iloc = it.cell.coord
            neighbors = iloc.neighbors()
            for n in neighbors:
                if n not in loc_to_tile_index:
                    continue
                other_tile_index = loc_to_tile_index[n]
                other_tile = self._tiles[other_tile_index]
                if abs(it.cell.layer - other_tile.cell.layer) > 1:
                    self._tiles[i].cell.boundary.set_edge_between(iloc, other_tile.cell.coord)

    def cards(self):
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
    
    def set_color(self, card_id, color):
        for idx, card in enumerate(self._cards):
            if card.id == card_id:
                self._cards[idx].border_color = color
                break
    
    def remove_card(self, card_id):
        for card in self._cards:
            if card.id == card_id:
                del self._cards_by_location[card.location]
        self._cards = [card for card in self._cards if card.id != card_id]
    
    def add_random_cards(self, number_of_cards):
        card_spawn_locations = self.choose_card_spawn_locations(number_of_cards)

        for loc in card_spawn_locations:
            (r, c) = loc
            self._cards.append(self._card_generator.generate_random_card_at(r, c))
            self._cards_by_location[self._cards[-1].location] = self._cards[-1]
    
    def add_random_unique_set(self):
        card_spawn_locations = self.choose_card_spawn_locations(3)

        unique_set = card.RandomUniqueSet()

        for i, loc in enumerate(card_spawn_locations):
            (shape, color, count) = unique_set[i]
            (r, c) = loc
            self._cards.append(self._card_generator.generate_card_at(r, c, shape, color, count))
            self._cards_by_location[self._cards[-1].location] = self._cards[-1]

    
    def spawn_points(self):
        return self._spawn_points

    def selected_cards(self):
        return self._selected_cards.values()

    def selected_cards_collide(self):
        shapes = set()
        colors = set()
        counts = set()
        for card in self.selected_cards():
            shapes.add(card.shape)
            colors.add(card.color)
            counts.add(card.count)
        num_cards = len(self.selected_cards())
        return not (len(shapes) == len(colors) == len(counts) == num_cards) or len(self.selected_cards()) > 3

    def selected_valid_set(self):
        return len(self.selected_cards()) == 3 and not self.selected_cards_collide()

    def card_by_location(self, location):
        return self._cards_by_location.get(location, None)

    def map(self):
        return MapUpdate(self._rows, self._cols, self._tiles, [card.prop() for card in self._cards])
    
    def coord_in_map(self, coord):
        offset_coords = coord.to_offset_coordinates()
        return (0 <= offset_coords[0] < self._rows) and (0 <= offset_coords[1] < self._cols)