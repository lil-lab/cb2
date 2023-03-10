import copy
import dataclasses
import logging
import random
from enum import Enum
from queue import Queue

import numpy as np

from server.assets import (
    AssetId,
    NatureAssets,
    SnowAssets,
    SnowifyAssetId,
    TreeAssets,
    TreeFrequencies,
)
from server.hex import HecsCoord, HexBoundary, HexCell
from server.messages.map_update import Tile

logger = logging.getLogger()


def LayerToHeight(layer):
    """Converts a layer to a height."""
    layer_to_height = {
        0: 0.05,
        1: 0.275,
        2: 0.355,
    }
    if layer not in layer_to_height:
        return layer_to_height[0]

    return layer_to_height[layer]


def EmptyTile():
    return Tile(
        AssetId.EMPTY_TILE,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        0,
    )


def SnowifyTile(tile):
    """Creates a snowy version of a tile."""
    return Tile(SnowifyAssetId(tile.asset_id), tile.cell, tile.rotation_degrees)


def GroundTile(rotation_degrees=0):
    """Creates a single tile of ground."""
    return Tile(
        AssetId.GROUND_TILE,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileSnow(rotation_degrees=0):
    """Creates a single tile of ground."""
    return Tile(
        AssetId.SNOWY_GROUND_TILE,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def WaterTile(rotation_degrees=0):
    """Creates a single tile of Water."""
    return Tile(
        AssetId.WATER_TILE,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def PathTile(rotation_degrees=0):
    """Creates a single tile of Path."""
    return Tile(
        AssetId.GROUND_TILE_PATH,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileRocky(rotation_degrees=0):
    """Creates a single tile of rocky ground."""
    return Tile(
        AssetId.GROUND_TILE_ROCKY,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileRockySnow(rotation_degrees=0):
    """Creates a single tile of rocky ground."""
    return Tile(
        AssetId.SNOWY_GROUND_TILE_ROCKY,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileStones(rotation_degrees=0):
    """Creates a single tile of ground with stones."""
    return Tile(
        AssetId.GROUND_TILE_STONES,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileStonesSnow(rotation_degrees=0):
    """Creates a single tile of ground with stones."""
    return Tile(
        AssetId.SNOWY_GROUND_TILE_STONES,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileTrees(rotation_degrees=0):
    """Creates a single tile of ground with several trees."""
    return Tile(
        AssetId.GROUND_TILE_TREES,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileTree(rotation_degrees=0):
    """Creates a single tile of ground with several trees."""
    return Tile(
        AssetId.GROUND_TILE_TREE,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileTreeBrown(rotation_degrees=0):
    """Creates a single tile of ground with a tree."""
    return Tile(
        AssetId.GROUND_TILE_TREE_BROWN,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileTreeSnow(rotation_degrees=0):
    """Creates a single tile of ground with a tree."""
    return Tile(
        AssetId.GROUND_TILE_TREE_SNOW,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def RandomGroundTree(rotation_degrees=0):
    """Creates a single tile of ground with a tree."""
    tree_asset_id = int(np.random.choice(TreeAssets(), p=TreeFrequencies()))
    return Tile(
        tree_asset_id,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def RandomNatureTile(rotation_degrees=0):
    """Creates a single tile of nature."""
    nature_asset_id = random.choice(NatureAssets())
    return Tile(
        nature_asset_id,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def RandomSnowTile(rotation_degrees=0):
    """Creates a single tile of nature."""
    snow_asset_id = random.choice(SnowAssets())
    return Tile(
        snow_asset_id,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileTreeRocks(rotation_degrees=0):
    """Creates a single tile of ground with a tree."""
    return Tile(
        AssetId.GROUND_TILE_TREES_2,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileTreeRocksSnow(rotation_degrees=0):
    """Creates a single tile of ground with a tree."""
    return Tile(
        AssetId.SNOWY_GROUND_TILE_TREES_2,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileForest(rotation_degrees=0):
    """Creates a single tile of ground with a forest."""
    return Tile(
        AssetId.GROUND_TILE_FOREST,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


class HouseType(Enum):
    NONE = 0
    HOUSE = 1
    HOUSE_RED = 2
    HOUSE_BLUE = 3
    HOUSE_PINK = 4
    HOUSE_GREEN = 5
    HOUSE_YELLOW = 6
    HOUSE_ORANGE = 7
    TRIPLE_HOUSE = 8
    TRIPLE_HOUSE_RED = 9
    TRIPLE_HOUSE_BLUE = 10
    RANDOM = 11


def AssetIdFromHouseType(type):
    if type == HouseType.HOUSE:
        return AssetId.GROUND_TILE_HOUSE
    elif type == HouseType.HOUSE_RED:
        return AssetId.GROUND_TILE_HOUSE_RED
    elif type == HouseType.HOUSE_BLUE:
        return AssetId.GROUND_TILE_HOUSE_BLUE
    elif type == HouseType.HOUSE_PINK:
        return AssetId.GROUND_TILE_HOUSE_PINK
    elif type == HouseType.HOUSE_GREEN:
        return AssetId.GROUND_TILE_HOUSE_GREEN
    elif type == HouseType.HOUSE_YELLOW:
        return AssetId.GROUND_TILE_HOUSE_YELLOW
    elif type == HouseType.HOUSE_ORANGE:
        return AssetId.GROUND_TILE_HOUSE_ORANGE
    elif type == HouseType.TRIPLE_HOUSE:
        return AssetId.GROUND_TILE_HOUSE_TRIPLE
    elif type == HouseType.TRIPLE_HOUSE_RED:
        return AssetId.GROUND_TILE_HOUSE_TRIPLE_RED
    elif type == HouseType.TRIPLE_HOUSE_BLUE:
        return AssetId.GROUND_TILE_HOUSE_TRIPLE_BLUE
    elif type == HouseType.RANDOM:
        return random.choice(
            [
                AssetId.GROUND_TILE_HOUSE,
                AssetId.GROUND_TILE_HOUSE_RED,
                AssetId.GROUND_TILE_HOUSE_BLUE,
                AssetId.GROUND_TILE_HOUSE_GREEN,
                AssetId.GROUND_TILE_HOUSE_ORANGE,
                AssetId.GROUND_TILE_HOUSE_PINK,
                AssetId.GROUND_TILE_HOUSE_YELLOW,
                AssetId.GROUND_TILE_HOUSE_TRIPLE,
                AssetId.GROUND_TILE_HOUSE_TRIPLE_RED,
                AssetId.GROUND_TILE_HOUSE_TRIPLE_BLUE,
            ]
        )
    else:
        logger.error(f"Unknown house type: {type}")
        return AssetId.HOUSE


def GroundTileHouse(rotation_degrees=0, type=HouseType.HOUSE):
    """Creates a single tile of ground with a house."""
    asset_id = AssetIdFromHouseType(type)
    return Tile(
        asset_id,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def UrbanHouseTile(rotation_degrees=0):
    """Creates a random house tile (like GroundTileHouse type=HouseType.RANDOM, but with a distribution meant for cities."""
    house_types = [
        HouseType.HOUSE,
        HouseType.HOUSE_RED,
        HouseType.HOUSE_BLUE,
        HouseType.HOUSE_PINK,
        HouseType.HOUSE_GREEN,
        HouseType.HOUSE_ORANGE,
        HouseType.HOUSE_YELLOW,
        HouseType.TRIPLE_HOUSE,
        HouseType.TRIPLE_HOUSE_RED,
        HouseType.TRIPLE_HOUSE_BLUE,
    ]
    house_type = np.random.choice(
        house_types, p=[0.13, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.09, 0.09, 0.09]
    )
    asset_id = AssetIdFromHouseType(house_type)
    return Tile(
        asset_id,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileStreetLight(rotation_degrees=0):
    """Creates a single tile of ground with a street light."""
    return Tile(
        AssetId.GROUND_TILE_STREETLIGHT,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def MountainTile(rotation_degrees=0, snowy=False):
    """Creates a single tile of mountain."""
    asset_id = AssetId.MOUNTAIN_TILE
    if snowy:
        asset_id = SnowifyAssetId(asset_id)
    return Tile(
        asset_id,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0),
            LayerToHeight(2),  # Height (float)
            2,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def MountainTileTree(rotation_degrees=0, snowy=False):
    """Creates a single tile of mountain with an optionally snowy tree."""
    asset_id = AssetId.MOUNTAIN_TILE_TREE
    if snowy:
        asset_id = SnowifyAssetId(asset_id)
    return Tile(
        asset_id,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(2),  # Height (float)
            2,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def RampToMountain(rotation_degrees=0, snowy=False):
    """Creates a single tile of ramp."""
    asset_id = AssetId.RAMP_TO_MOUNTAIN
    if snowy:
        asset_id = SnowifyAssetId(asset_id)
    return Tile(
        asset_id,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary.rotate_cw(HexBoundary(0b101101), rotation_degrees),
            LayerToHeight(1),  # Height (float)
            1,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


# Tile boundaries must prevent leaving the map, or undefined behavior will occur.
def FloodFillPartitionTiles(tiles):
    tile_by_loc = {}
    for tile in tiles:
        tile_by_loc[tile.cell.coord] = tile

    unvisited_tiles = set(tiles)
    visited_tiles = set()
    tile_queue = Queue()
    partitions = []

    while len(unvisited_tiles) > 0:
        tile = unvisited_tiles.pop()
        tile_queue.put(tile)
        partition = []
        # Do a floodfill to create a partition on the map from this tile.
        while not tile_queue.empty():
            tile = tile_queue.get()
            if tile in visited_tiles:
                continue
            partition.append(tile)
            if tile in unvisited_tiles:
                unvisited_tiles.remove(tile)
            visited_tiles.add(tile)
            coord = tile.cell.coord
            boundary = tile.cell.boundary
            # Add all neighbors that aren't blocked by an edge.
            for neighbor in coord.neighbors():
                if neighbor not in tile_by_loc:
                    continue
                if neighbor in visited_tiles:
                    continue
                if not boundary.get_edge_between(coord, neighbor):
                    tile_queue.put(tile_by_loc[neighbor])
        partitions.append(partition)
    return partitions


def CensorMapForFollower(map_update, follower):
    """Censors information from a map that the follower isn't supposed to have."""
    map_update_clone = copy.deepcopy(map_update)
    return map_update_clone


def CensorCards(prop_update, follower=None):
    """Censors card information from a map that the follower isn't supposed to have.

    Can optionally supply the follower to get more specific censorship, like only hiding nearby cards.

    Since this just marks card_init.hidden = True, it doesn't actually remove
    information -- just lets clients know that they shouldn't show this to the
    follower. This is useful for the leader client, which needs to render a
    follower viewpoint, so the leader can see the follower POV.
    """
    props = []
    for i, prop_item in enumerate(prop_update.props):
        hidden = prop_item.card_init.hidden
        if prop_item.prop_type == prop_item.prop_type.CARD:
            if not prop_item.card_init.selected:
                hidden = True

        new_card_init = dataclasses.replace(prop_item.card_init, hidden=hidden)
        props.append(dataclasses.replace(prop_item, card_init=new_card_init))
    return dataclasses.replace(prop_update, props=props)
