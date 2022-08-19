""" This utility streams a hardcoded map to clients. """
from pathlib import Path
from server.assets import AssetId, is_snowy, SnowifyAssetId
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from enum import Enum
from server.hex import HecsCoord, HexCell, HexBoundary
from server.map_utils import *
from server.messages.map_update import MapMetadata, MapUpdate, City, Lake, Mountain, Outpost, MountainType, LakeType
from server.messages.prop import PropUpdate
from queue import Queue
from typing import List, Optional

import asyncio
import dataclasses
import itertools
import logging
import math
import random
import server.card as card
import numpy as np
import server.tutorial_map_data as tutorial_map_data

from server.util import IdAssigner

MAP_WIDTH = 25
MAP_HEIGHT = 25

MIN_NUMBER_OF_MOUNTAINS = 3
MAX_NUMBER_OF_MOUNTAINS = 3

MIN_NUMBER_OF_CITIES = 3
MAX_NUMBER_OF_CITIES = 4

MIN_NUMBER_OF_LAKES = 3
MAX_NUMBER_OF_LAKES = 4

MIN_NUMBER_OF_OUTPOSTS = 3
MAX_NUMBER_OF_OUTPOSTS = 6

PATH_CONNECTION_DISTANCE = 4

logger = logging.getLogger()

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

    # Make openings to enter and exit the city.
    connection_points = city_connection_points(city)
    for point in connection_points:
        r,c = point.to_offset_coordinates()
        map[r][c] = PathTile()

    point_queue = Queue()
    point_queue.put(SearchPoint(city.r, city.c, 0))
    covered_points = set()
    while not point_queue.empty():
        point = point_queue.get()
        if (point.r, point.c) in covered_points:
            continue
        covered_points.add((point.r, point.c))
        if map[point.r][point.c].asset_id in [AssetId.EMPTY_TILE, AssetId.GROUND_TILE] + NatureAssets():
            if point.radius % 3 == 0:
                tile_generator = np.random.choice([PathTile, RandomGroundTree, GroundTileStreetLight], size=1, p=[0.3, 0.3, 0.4])[0]
                map[point.r][point.c] = tile_generator(rotation_degrees = random.choice([0, 60, 120, 180, 240, 300]))
            elif point.radius % 3 == 1:
                map[point.r][point.c] = PathTile()
            elif point.radius % 3 == 2:
                coord = HecsCoord.from_offset(point.r, point.c)
                center = HecsCoord.from_offset(city.r, city.c)
                degrees_to_center = coord.degrees_to(center) - 60
                map[point.r][point.c] = UrbanHouseTile(rotation_degrees=degrees_to_center)
        hc = HecsCoord.from_offset(point.r, point.c)
        for neighbor in hc.neighbors():
            nr,nc = neighbor.to_offset_coordinates()
            if (nr, nc) in covered_points:
                continue
            if nr < 0 or nr >= MAP_HEIGHT or nc < 0 or nc >= MAP_WIDTH:
                continue
            if point.radius < city.size:
                point_queue.put(SearchPoint(nr, nc, point.radius + 1))

def city_connection_points(city):
    """ Returns the HecsCoord coordinates of the city's connection points."""
    center = HecsCoord.from_offset(city.r, city.c)
    potential_connections = [
        center.left().left().to_offset_coordinates(),
        center.right().right().to_offset_coordinates(),
        center.up_left().up_right().to_offset_coordinates(),
        center.down_left().down_right().to_offset_coordinates()
    ]
    connections = []
    for r,c in potential_connections:
        if r < 0 or r >= MAP_HEIGHT or c < 0 or c >= MAP_WIDTH:
            continue
        connections.append(HecsCoord.from_offset(r, c))
    return connections

def place_circular_lake(map, lake):
    """ Places a lake on the map."""
    # Place the center tile.
    map[lake.r][lake.c] = WaterTile()

    point_queue = Queue()
    point_queue.put(SearchPoint(lake.r, lake.c, 0))
    covered_points = set()
    while not point_queue.empty():
        point = point_queue.get()
        if (point.r, point.c) in covered_points:
            continue
        covered_points.add((point.r, point.c))
        hc = HecsCoord.from_offset(point.r, point.c)
        for neighbor in hc.neighbors():
            r,c = neighbor.to_offset_coordinates()
            if (r, c) in covered_points:
                continue
            # Keep lakes away from the edge of the map.
            if r < 0 or r >= MAP_HEIGHT or c < 0 or c >= MAP_WIDTH:
                continue
            edge_of_map = (r == 0 or c == 0 or r == MAP_HEIGHT - 1 or c == MAP_WIDTH - 1)
            if map[r][c].asset_id in [AssetId.EMPTY_TILE, AssetId.GROUND_TILE]:
                if (point.radius == lake.size) or edge_of_map:
                    map[r][c] = PathTile()
                elif map[r][c].asset_id == AssetId.EMPTY_TILE:
                    map[r][c] = WaterTile()
            if point.radius < lake.size:
                point_queue.put(SearchPoint(r, c, point.radius + 1))

def place_l_shaped_lake(map, lake):
    r, c = lake.r, lake.c
    # Each lake configuration is a list of smaller lake epicenters. They are combined to make the larger lake.
    lake_configurations = [
        [Lake(r, c, 1), Lake(r, c + 2, 1), Lake(r + 2, c, 1)],
        [Lake(r, c, 1), Lake(r, c - 2, 1), Lake(r - 2, c, 1)],
        [Lake(r, c, 1), Lake(r, c + 2, 1), Lake(r - 2, c, 1)],
        [Lake(r, c, 1), Lake(r, c - 2, 1), Lake(r + 2, c, 1)],
    ]
    lake_positions = random.choice(lake_configurations)
    for lake in lake_positions:
        if not offset_coord_in_map(map, (lake.r, lake.c)):
            continue
        place_circular_lake(map, lake)

def place_island_lake(map, lake):
    r, c = lake.r, lake.c
    lake.size = 2
    place_circular_lake(map, lake)
    point_queue = Queue()
    point_queue.put(SearchPoint(r, c, 0))
    center = HecsCoord.from_offset(r, c)
    map[r][c] = np.random.choice([GroundTile, RandomNatureTile, GroundTileStreetLight], size=1, p=[0.05, 0.45, 0.5])[0]()
    lr, lc = center.left().to_offset_coordinates()
    map[lr][lc] = np.random.choice([GroundTile, RandomNatureTile, GroundTileStreetLight], size=1, p=[0.9, 0.05, 0.05])[0]()
    rr, rc = center.right().to_offset_coordinates()
    map[rr][rc] = np.random.choice([GroundTile, RandomNatureTile, GroundTileStreetLight], size=1, p=[0.9, 0.05, 0.05])[0]()

    # Each "bridge" consists of two tiles (tile_inner, tile_outer)
    bridge_points = [(center.up_left(), center.up_left().up_left()), (center.up_right(), center.up_right().up_right()), (center.down_left(), center.down_left().down_left()), (center.down_right(), center.down_right().down_right())]
    random.shuffle(bridge_points)
    number_of_bridges = random.randint(0, 4)
    for i in range(number_of_bridges):
        if len(bridge_points) == 0:
            continue
        inner, outer = bridge_points.pop()
        in_r, in_c = inner.to_offset_coordinates()
        out_r, out_c = outer.to_offset_coordinates()
        map[in_r][in_c] = GroundTile()
        map[out_r][out_c] = GroundTile()
    
    for inner, outer in bridge_points:
        in_r, in_c = inner.to_offset_coordinates()
        map[in_r][in_c] = np.random.choice([GroundTile, RandomNatureTile, GroundTileStreetLight], size=1, p=[0.9, 0.05, 0.05])[0]()

def random_lake_type():
    # Do NOT put RANDOM as a return option in this function, or it causes an infinite recursive loop in place_lake below.
    # Just in case you were inattentive and didn't read this, I placed a guard if-statement below it.
    lake_type = random.choice([LakeType.REGULAR, LakeType.L_SHAPED, LakeType.ISLAND])
    if lake_type == LakeType.RANDOM:
        logger.warning("RANDOM lake type cannot be returned from random_lake_type().")
        return LakeType.REGULAR
    return lake_type

def place_lake(map, lake):
    type = lake.type
    if type == LakeType.RANDOM:
        # Recursive, but guaranteed to terminate.
        lake.type = random_lake_type()
        if lake.type == LakeType.RANDOM:
            logger.warning("RANDOM lake type cannot be returned from random_lake_type().")
            lake.type = LakeType.REGULAR
        place_lake(map, lake)
    elif type == LakeType.L_SHAPED:
        place_l_shaped_lake(map, lake)
    elif type == LakeType.ISLAND:
        place_island_lake(map, lake)
    elif type == LakeType.REGULAR:
        place_circular_lake(map, lake)

def lake_connection_points(lake):
    """ Returns the HecsCoord coordinates of the lake's connection points."""
    potential_connections = [(lake.r, lake.c + lake.size + 1), (lake.r + lake.size + 1, lake.c), (lake.r, lake.c - lake.size - 1), (lake.r - lake.size - 1, lake.c)]
    connections = []
    for r,c in potential_connections:
        if r < 0 or r >= MAP_HEIGHT or c < 0 or c >= MAP_WIDTH:
            continue
        connections.append(HecsCoord.from_offset(r, c))
    return connections

def is_walkable(map, hecs_coord):
    """ Returns whether or not the given HecsCoord is walkable."""
    r,c = hecs_coord.to_offset_coordinates()
    return map[r][c].asset_id in [AssetId.EMPTY_TILE, AssetId.GROUND_TILE, AssetId.GROUND_TILE_PATH]

def offset_coord_in_map(map, offset):
    return (offset[0] in range(0, len(map)) and
            offset[1] in range(0, len(map[offset[0]])))

def place_small_mountain(map, mountain):
    mountain_coords = []
    # MountainTile(rotation_degrees=0)
    # RampToMountain(rotation_degrees=0)
    map[mountain.r][mountain.c] = MountainTile(rotation_degrees=0, snowy=mountain.snowy)
    start = HecsCoord.from_offset(mountain.r, mountain.c)
    mountain_coords.append(start)
    mountain_coords.append(start.right())
    mountain_coords.append(start.down_left())
    mountain_coords.append(start.down_right())

    potential_trees = [start.right(), start.down_left()]
    trees = random.sample(potential_trees, random.randint(0, len(potential_trees) - 1))

    for coord in mountain_coords:
        offset = coord.to_offset_coordinates()
        if offset_coord_in_map(map, offset):
            if coord in trees:
                map[offset[0]][offset[1]] = MountainTileTree(rotation_degrees=0, snowy=mountain.snowy)
                continue
            map[offset[0]][offset[1]] = MountainTile(rotation_degrees=0, snowy=mountain.snowy)

    first_ramp_offset = start.left().to_offset_coordinates()
    second_ramp_offset = start.right().down_right().to_offset_coordinates()
    first_connection_point = start.left().left();
    second_connection_point = start.right().down_right().right()
    ramp_locations = []
    if offset_coord_in_map(map, first_connection_point.to_offset_coordinates()) and is_walkable(map, first_connection_point):
        ramp_locations.append(HecsCoord.from_offset(*first_ramp_offset))
        map[first_ramp_offset[0]][first_ramp_offset[1]] = RampToMountain(rotation_degrees=00, snowy=mountain.snowy)
    if offset_coord_in_map(map, second_connection_point.to_offset_coordinates()) and is_walkable(map, second_connection_point):
        ramp_locations.append(HecsCoord.from_offset(*second_ramp_offset))
        map[second_ramp_offset[0]][second_ramp_offset[1]] = RampToMountain(rotation_degrees=180, snowy=mountain.snowy)

    # Tiles around ramps are always kept clear (walkable).
    placed_coords = ramp_locations
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
    map[mountain.r][mountain.c] = MountainTile(rotation_degrees=0, snowy=mountain.snowy)
    start = HecsCoord.from_offset(mountain.r, mountain.c)
    mountain_coords.append(start)
    mountain_coords.append(start.down_right())
    mountain_coords.append(start.down_left())
    mountain_coords.append(start.down_right().down_right())
    mountain_coords.append(start.down_right().down_left())

    potential_trees = [start, start.down_right(), start.down_right().down_right()]
    trees = random.sample(potential_trees, random.randint(0, len(potential_trees) - 1))

    for coord in mountain_coords:
        offset = coord.to_offset_coordinates()
        if offset_coord_in_map(map, offset):
            if coord in trees:
                map[offset[0]][offset[1]] = MountainTileTree(rotation_degrees=0, snowy=mountain.snowy)
                continue
            map[offset[0]][offset[1]] = MountainTile(rotation_degrees=0, snowy=mountain.snowy)

    first_ramp_offset = start.left().to_offset_coordinates()
    second_ramp_offset = start.down_right().down_right().down_left().to_offset_coordinates()
    first_connection_point = start.left().up_left()
    second_connection_point = start.down_right().down_right().down_right().down_left()
    ramp_locations = []
    if offset_coord_in_map(map, first_connection_point.to_offset_coordinates()) and is_walkable(map, first_connection_point):
        ramp_locations.append(HecsCoord.from_offset(*first_ramp_offset))
        map[first_ramp_offset[0]][first_ramp_offset[1]] = RampToMountain(rotation_degrees=60, snowy=mountain.snowy)
    if offset_coord_in_map(map, second_connection_point.to_offset_coordinates()) and is_walkable(map, second_connection_point):
        ramp_locations.append(HecsCoord.from_offset(*second_ramp_offset))
        map[second_ramp_offset[0]][second_ramp_offset[1]] = RampToMountain(rotation_degrees=240, snowy=mountain.snowy)

    # Tiles around ramps are always kept clear (walkable).
    placed_coords = ramp_locations
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
    map[mountain.r][mountain.c] = MountainTile(rotation_degrees=0, snowy=mountain.snowy)
    start = HecsCoord.from_offset(mountain.r, mountain.c)
    mountain_coords.append(start)
    for coord in start.neighbors():
        mountain_coords.append(coord)
    
    potential_trees = [start.down_left(), start.down_right(), start.up_left(), start.up_right()]
    trees = random.sample(potential_trees, random.randint(0, len(potential_trees) - 1))

    for coord in mountain_coords:
        offset = coord.to_offset_coordinates()
        if offset_coord_in_map(map, offset):
            if coord in trees:
                map[offset[0]][offset[1]] = MountainTileTree(rotation_degrees=0, snowy=mountain.snowy)
                continue
            map[offset[0]][offset[1]] = MountainTile(rotation_degrees=0, snowy=mountain.snowy)

    first_ramp_offset = start.left().left().to_offset_coordinates()
    second_ramp_offset = start.right().right().to_offset_coordinates()
    first_connection_point = start.left().left().left()
    second_connection_point = start.right().right().right()
    ramp_locations = []
    if offset_coord_in_map(map, first_connection_point.to_offset_coordinates()) and is_walkable(map, first_connection_point):
        ramp_locations.append(HecsCoord.from_offset(*first_ramp_offset))
        map[first_ramp_offset[0]][first_ramp_offset[1]] = RampToMountain(rotation_degrees=0, snowy=mountain.snowy)
    if offset_coord_in_map(map, second_connection_point.to_offset_coordinates()) and is_walkable(map, second_connection_point):
        ramp_locations.append(HecsCoord.from_offset(*second_ramp_offset))
        map[second_ramp_offset[0]][second_ramp_offset[1]] = RampToMountain(rotation_degrees=180, snowy=mountain.snowy)

    # Tiles around ramps are always kept clear (walkable).
    placed_coords = ramp_locations
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

def mountain_connection_points(map, mountain):
    start = HecsCoord.from_offset(mountain.r, mountain.c)
    first_connection_point = None
    second_connection_point = None
    if mountain.type == MountainType.SMALL:
        first_connection_point = start.left().left();
        second_connection_point = start.right().down_right().right()
    elif mountain.type == MountainType.MEDIUM:
        first_connection_point = start.left().up_left()
        second_connection_point = start.down_right().down_right().down_right().down_left()
    elif mountain.type == MountainType.LARGE:
        first_connection_point = start.left().left().left()
        second_connection_point = start.right().right().right()
    connection_points = []
    if first_connection_point is not None and offset_coord_in_map(map, first_connection_point.to_offset_coordinates()) and is_walkable(map, first_connection_point):
        connection_points.append(first_connection_point)
    if second_connection_point is not None and offset_coord_in_map(map, second_connection_point.to_offset_coordinates()) and is_walkable(map, second_connection_point):
        connection_points.append(second_connection_point)
    return connection_points

def path_find(map, start, end):
    """ Finds a path of empty or ground tiles from start to end on the map.

        Returns a list of tiles that make up the path.

        Used for outpost routing.
    """
    children = Queue()
    children.put((start, [start]))
    visited = set()
    visited.add(start)
    while not children.empty():
        (current, path_to_current) = children.get()
        if current == end:
            return path_to_current
        (r, c) = current.to_offset_coordinates()
        for neighbor in current.neighbors():
            nr, nc = neighbor.to_offset_coordinates()
            if nr < 0 or nr >= len(map) or nc < 0 or nc >= len(map[0]):
                continue
            neighbor_tile = map[nr][nc]
            if neighbor_tile.asset_id in [AssetId.EMPTY_TILE, AssetId.GROUND_TILE, AssetId.GROUND_TILE_PATH] + NatureAssets():
                if neighbor not in visited:
                    path_to_neighbor = path_to_current + [neighbor]
                    child_node = (neighbor, path_to_neighbor)
                    children.put(child_node)
                    visited.add(neighbor)
    return None

def place_outpost(map, outpost):
    """ Place tiles at (r, c), (r + 1, c), (r, c + 2), (r + 1, c + 2) """
    coords = [(outpost.r, outpost.c), (outpost.r + 1, outpost.c), (outpost.r + 1, outpost.c + 1), (outpost.r+3, outpost.c + 1)] 
    tiles = outpost.tiles
    # Truncate tiles to the maximum size of an outpost.
    if len(outpost.tiles) > len(coords):
        tiles = tiles[:len(coords)]
    # Place the outpost.
    for i, tile in enumerate(tiles):
        if i >= len(coords):
            break
        row, col = coords[i]
        tile.cell.coord = HecsCoord.from_offset(row, col)
        map[row][col] = tile
    
    # The outpost positioning purposefully leaves out (r, c+1). This is the center. Mark it as PathTile and then path-connect it to nearest features.
    map[outpost.r+2][outpost.c] = PathTile()

    # Connect the outpost to the nearest features.
    path_to_a = path_find(map, HecsCoord.from_offset(outpost.r + 2, outpost.c), outpost.connection_a)
    path_to_b = path_find(map, HecsCoord.from_offset(outpost.r + 2, outpost.c), outpost.connection_b)

    # Replace all non-mountain and non-ramp tiles in paths a and b with PathTile.
    for path_to_x in [path_to_a, path_to_b]:
        if path_to_x is None:
            continue
        for coord in path_to_x:
            offset = coord.to_offset_coordinates()
            if offset_coord_in_map(map, offset):
                map[offset[0]][offset[1]] = PathTile()
            
def RandomMap():
    """ Random map of Tile objects, each with HECS coordinates and locations."""
    map = []
    for r in range(0, MAP_HEIGHT):
        row = []
        for c in range(0, MAP_WIDTH):
            tile = EmptyTile()
            row.append(tile)
        map.append(row)

    map_metadata = MapMetadata([], [], [], [], 0)
    
    # Generate candidates for feature centers.
    rows = list(range(1, MAP_HEIGHT - 2, 6))
    cols = list(range(1, MAP_WIDTH - 2, 6))
    feature_center_candidates = list(itertools.product(rows, cols))
    random.shuffle(feature_center_candidates)

    # Points where an outpost can be connected to.
    connection_points = []
    connection_point_entity = {}  # Give each feature a unique ID. This maps connection_point to entity.
    ids = IdAssigner()

    number_of_cities = random.randint(MIN_NUMBER_OF_CITIES, MAX_NUMBER_OF_CITIES)
    cities = []
    for i in range(number_of_cities):
        if len(feature_center_candidates) == 0:
            break
        city_center = feature_center_candidates.pop()
        city = City(city_center[0], city_center[1], 2)
        cities.append(city)
        place_city(map, city)
        map_metadata.cities.append(city)
        new_connection_points = city_connection_points(city)
        connection_points.extend(new_connection_points)
        feature_id = ids.alloc()
        for point in new_connection_points:
            connection_point_entity[point] = feature_id


    number_of_lakes = random.randint(MIN_NUMBER_OF_LAKES, MAX_NUMBER_OF_LAKES)
    lake_types = [LakeType.ISLAND, LakeType.L_SHAPED, LakeType.REGULAR] * ((number_of_lakes // 3) + 1)
    random.shuffle(lake_types)
    for i in range(number_of_lakes):
        if len(feature_center_candidates) == 0:
            break
        lake_center = feature_center_candidates.pop()
        lake = Lake(lake_center[0], lake_center[1], random.randint(1, 2), lake_types.pop())
        place_lake(map, lake)
        map_metadata.lakes.append(lake)
        new_connection_points = lake_connection_points(lake)
        connection_points.extend(new_connection_points)
        feature_id = ids.alloc()
        for point in new_connection_points:
            connection_point_entity[point] = feature_id

    number_of_mountains = random.randint(MIN_NUMBER_OF_MOUNTAINS, MAX_NUMBER_OF_MOUNTAINS)
    mountain_types = [MountainType.SMALL, MountainType.MEDIUM, MountainType.LARGE]
    random.shuffle(mountain_types)

    for i in range(number_of_mountains):
        if len(feature_center_candidates) == 0:
            break
        mountain_center = feature_center_candidates.pop()
        mountain = Mountain(mountain_center[0], mountain_center[1], mountain_types.pop(), bool(np.random.choice([True, False], p=[0.3, 0.7])))
        place_mountain(map, mountain)
        map_metadata.mountains.append(mountain)
        new_connection_points = mountain_connection_points(map, mountain)
        connection_points.extend(new_connection_points)
        feature_id = ids.alloc()
        for point in new_connection_points:
            connection_point_entity[point] = feature_id

    # Add a random number of outposts.
    number_of_outposts = random.randint(MIN_NUMBER_OF_OUTPOSTS, MAX_NUMBER_OF_OUTPOSTS)
    for i in range(number_of_outposts):
        if len(feature_center_candidates) == 0:
            break
        outpost_center = feature_center_candidates.pop()
        outpost_center_hex = HecsCoord.from_offset(outpost_center[0], outpost_center[1])
        nearest_connection_points = sorted(connection_points, key=lambda x: x.distance_to(outpost_center_hex))
        first_connection_point = nearest_connection_points.pop(0) if len(nearest_connection_points) > 0 else None
        second_connection_point = nearest_connection_points.pop(0) if len(nearest_connection_points) > 0 else None
        outpost = Outpost(outpost_center[0], outpost_center[1], first_connection_point, second_connection_point, [RandomNatureTile(), UrbanHouseTile(), RandomNatureTile()])
        map_metadata.outposts.append(outpost)
        if random.randint(0, 1) == 0:
            outpost.tiles.append(UrbanHouseTile(rotation_degrees=180))
        place_outpost(map, outpost)
    
    # For each connection point, see if another connection point is nearby. If so, path connect them.
    number_of_entities = ids.num_allocated()
    connected = [[0 for _ in range(number_of_entities)] for _ in range(number_of_entities)]
    for i, connection_i in enumerate(connection_points):
        for j, connection_j in enumerate(connection_points):
            if connection_point_entity[connection_i] == connection_point_entity[connection_j]:
                continue
            entity_i = connection_point_entity[connection_i]
            entity_j = connection_point_entity[connection_j]
            if connected[entity_i][entity_j]:
                continue
            distance = connection_i.distance_to(connection_j)
            if distance > 0 and distance <= PATH_CONNECTION_DISTANCE:
                path_to_j = path_find(map, connection_i, connection_j)
                if path_to_j is not None:
                    for coord in path_to_j:
                        offset = coord.to_offset_coordinates()
                        if offset_coord_in_map(map, offset):
                            map[offset[0]][offset[1]] = PathTile()
                    connected[entity_i][entity_j] = 1
                    connected[entity_j][entity_i] = 1

    # Fill empty tiles with random ground tiles.
    snow_tiles = set([(r, c) for r in range(MAP_HEIGHT) for c in range(MAP_WIDTH) if is_snowy(map[r][c].asset_id)])
    for r in range(0, MAP_HEIGHT):
        for c in range(0, MAP_WIDTH):
            if map[r][c].asset_id == AssetId.EMPTY_TILE:
                is_near_snow = False
                hecs = HecsCoord.from_offset(r, c)
                for neighbor in hecs.neighbors():
                    neighbor_rc = neighbor.to_offset_coordinates()
                    if offset_coord_in_map(map, neighbor_rc) and neighbor_rc in snow_tiles:
                        is_near_snow = True
                        break
                tile_generator = np.random.choice([GroundTile, RandomNatureTile, GroundTileStreetLight], size=1, p=[0.88, 0.10, 0.02])[0]
                tile = tile_generator()
                snowify_tile = is_near_snow and tile.asset_id in TreeAssets()
                map[r][c] = SnowifyTile(tile) if snowify_tile else tile

    # Make sure there's at least 23 walkable tiles (2 for spawn points, 21 for card placement). 
    walkable_tiles = 0
    blocked_nature_tiles = []
    for r in range(0, MAP_HEIGHT):
        for c in range(0, MAP_WIDTH):
            if is_walkable(map, HecsCoord.from_offset(r, c)):
                walkable_tiles += 1
            elif map[r][c].asset_id in NatureAssets():
                blocked_nature_tiles.append(map[r][c])
    
    if walkable_tiles < 23:
        for i in range(23 - walkable_tiles):
            blocked_nature_tile = random.choice(blocked_nature_tiles)
            r, c = blocked_nature_tile.cell.coord.to_offset_coordinates()
            map[r][c] = GroundTile()
            blocked_nature_tiles.remove(blocked_nature_tile)
            walkable_tiles += 1

    # Fix all the tile coordinates.
    for r in range(0, MAP_HEIGHT):
        for c in range(0, MAP_WIDTH):
            map[r][c].cell.coord = HecsCoord.from_offset(r, c)

    # Flatten the 2D map of tiles to a list.
    map_tiles = [tile for row in map for tile in row]

    # Recompute heights.
    for i in range(len(map_tiles)):
        map_tiles[i].cell.height = LayerToHeight(map_tiles[i].cell.layer)

    return MapUpdate(MAP_HEIGHT, MAP_WIDTH, map_tiles, map_metadata)

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
    def __init__(self, map_type):
        map = None
        if map_type == MapType.RANDOM:
            map = RandomMap()
            self._map_metadata = map.metadata
        elif map_type == MapType.HARDCODED:
            map = tutorial_map_data.HardcodedMap()
            self._map_metadata = None
        else:
            raise ValueError("Invalid map type NONE specified.")
        
        self._id_assigner = IdAssigner()
        self._tiles = map.tiles
        self._rows = map.rows
        self._cols = map.cols
        self._cards = []
        self._selected_cards = {}
        self._card_generator = CardGenerator(self._id_assigner)
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
                card_copy.id = self._id_assigner.alloc()
                self._cards.append(card_copy)
        else: 
            # Sort through the potential spawn tiles via floodfill and find
            # partitions (regions which are blocked off by walls or edges).
            # Then, remove all spaces which aren't in the largest partition as
            # spawn tiles.            
            spaces = FloodFillPartitionTiles(self._tiles)
            sorted_spaces = sorted(spaces, key=len, reverse=True)
            # Only spawn cards in the largest contiguous region.
            self._map_metadata.num_partitions = len(sorted_spaces)
            self._map_metadata.partition_locations = [space[0] for space in sorted_spaces]
            self._map_metadata.partition_sizes = [len(space) for space in sorted_spaces]
            self._potential_spawn_tiles = sorted_spaces[0]

            self._potential_spawn_tiles = [tile 
                                        for tile in self._potential_spawn_tiles
                                        if tile.asset_id in [AssetId.GROUND_TILE, AssetId.GROUND_TILE_PATH,
                                                             AssetId.MOUNTAIN_TILE, AssetId.SNOWY_MOUNTAIN_TILE]]

            number_of_cards = 21
            number_of_sets = math.ceil(number_of_cards / 3)
            card_spawn_locations = self.choose_card_spawn_locations(number_of_sets * 3)

            for _ in range(number_of_sets):
                card_configs = card.RandomUniqueSet()
                for config in card_configs:
                    if len(card_spawn_locations) == 0:
                        break
                    (r, c) = card_spawn_locations.pop()
                    (shape, color, count) = config
                    self._cards.append(self._card_generator.generate_card_at(r, c, shape, color, count))

        # Index cards generated.
        self._cards_by_location = {}
        for generated_card in self._cards:
            self._cards_by_location[generated_card.location] = generated_card
        self._spawn_points = [tile.cell.coord for tile in self._tiles
                              if (tile.asset_id == AssetId.GROUND_TILE_PATH) and (tile.cell.coord not in self._cards_by_location)]
    
    def id_assigner(self):
        return self._id_assigner

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

        if n > len(self._potential_spawn_tiles):
            logger.error("WARNING: Not enough spawn tiles to spawn all cards.")
            n = len(self._potential_spawn_tiles)
        spawn_tiles = np.random.choice(self._potential_spawn_tiles, size=n, replace=False, p=card_spawn_weights)
        return [tile.cell.coord.to_offset_coordinates() for tile in spawn_tiles]
    
    def calculate_card_spawn_weight(self, tile):
        if tile.asset_id == AssetId.GROUND_TILE:
            return 1
        elif tile.asset_id == AssetId.GROUND_TILE_PATH:
            return 2
        elif tile.asset_id == AssetId.MOUNTAIN_TILE:
            return 2
        elif tile.asset_id == AssetId.SNOWY_MOUNTAIN_TILE:
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
        if self._map_metadata:
            return MapUpdate(self._rows, self._cols, self._tiles, self._map_metadata)
        else:
            return MapUpdate(self._rows, self._cols, self._tiles)

    def prop_update(self):
        return PropUpdate([card.prop() for card in self._cards])
    
    def coord_in_map(self, coord):
        offset_coords = coord.to_offset_coordinates()
        return (0 <= offset_coords[0] < self._rows) and (0 <= offset_coords[1] < self._cols)

MAP_POOL_MAXIMUM = 500
map_pool = []

def CachedMapRetrieval():
    global map_pool
    if len(map_pool) == 0:
        print(f"Map pool ran out of cached maps. Generating...")
        return MapProvider(MapType.RANDOM)
    else:
        return map_pool.pop()

def MapPoolSize():
    global map_pool
    return len(map_pool)

async def MapGenerationTask(room_manager, config):
    while True:
        # Only generate maps when there are no active games.
        if len(room_manager.room_ids()) != 0:
            await asyncio.sleep(10)
            continue

        # Map cache is full, skip.
        if len(map_pool) >= MAP_POOL_MAXIMUM or len(map_pool) >= config.map_cache_size:
            await asyncio.sleep(10)
            continue

        # Add a map to the map cache.
        map_pool.append(MapProvider(MapType.RANDOM))
        if len(map_pool) % 10 == 0:
            print(f"Map pool size: {len(map_pool)}")
        await asyncio.sleep(0.001)

