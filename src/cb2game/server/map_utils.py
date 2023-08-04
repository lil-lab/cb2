import copy
import dataclasses
import logging
import random
from enum import Enum
from queue import Queue

import numpy as np

from cb2game.server.assets import (
    AssetFrequenciesFromTileClass,
    AssetId,
    AssetsFromTileClass,
    SnowAssets,
    SnowifyAssetId,
    TileClass,
)
from cb2game.server.config.map_config import MapConfig
from cb2game.server.hex import HecsCoord, HexBoundary, HexCell
from cb2game.server.messages.action import Color
from cb2game.server.messages.map_update import Tile

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


def ChooseAssetFromTileClass(
    tile_class: TileClass,
    map_config: MapConfig = MapConfig(),
    preference: AssetId = AssetId.NONE,
):
    frequencies = {
        asset: frequency
        for asset, frequency in zip(
            AssetsFromTileClass(tile_class), AssetFrequenciesFromTileClass(tile_class)
        )
    }
    tile_names = []
    if tile_class == TileClass.GROUND_TILES:
        tile_names = map_config.ground_tiles
    elif tile_class == TileClass.PATH_TILES:
        tile_names = map_config.path_tiles
    elif tile_class == TileClass.STONE_TILES:
        tile_names = map_config.stone_tiles
    elif tile_class == TileClass.FOLIAGE_TILES:
        tile_names = map_config.foliage_tiles
    elif tile_class == TileClass.TREE_TILES:
        tile_names = map_config.tree_tiles
    elif tile_class == TileClass.STREETLIGHT_TILES:
        tile_names = map_config.streetlight_tiles
    elif tile_class == TileClass.HOUSE_TILES:
        tile_names = map_config.house_tiles
    elif tile_class == TileClass.URBAN_HOUSE_TILES:
        tile_names = map_config.urban_house_tiles
    elif tile_class == TileClass.WATER_TILES:
        tile_names = map_config.water_tiles
    else:
        logger.error(f"Invalid tile class: {tile_class}")
    tiles = [AssetId[tile_name] for tile_name in tile_names]
    for tile in tiles:
        assert type(tile) == AssetId, f"Invalid tile type: {tile}"
    # Preference is used only if it is specified in the config.
    if preference != AssetId.NONE and preference in tiles:
        return preference
    tile_frequencies = [frequencies[tile] for tile in tiles]
    # Normalize frequencies.
    frequency_sum = sum(tile_frequencies)
    for i in range(len(tile_frequencies)):
        tile_frequencies[i] /= frequency_sum
    asset_id = int(np.random.choice(tiles, p=tile_frequencies))
    assert type(asset_id) == int, f"Invalid asset_id type: {asset_id}"
    return asset_id


def GroundTile(
    rotation_degrees=0,
    map_config: MapConfig = MapConfig(),
    preference: AssetId = AssetId.NONE,
):
    """Creates a single tile of ground."""
    asset_id = ChooseAssetFromTileClass(TileClass.GROUND_TILES, map_config, preference)
    return Tile(
        asset_id,
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


def WaterTile(
    rotation_degrees=0,
    map_config: MapConfig = MapConfig(),
    preference: AssetId = AssetId.NONE,
):
    """Creates a single tile of Water."""
    asset_id = ChooseAssetFromTileClass(TileClass.WATER_TILES, map_config, preference)
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


def PathTile(
    rotation_degrees=0,
    map_config: MapConfig = MapConfig(),
    preference: AssetId = AssetId.NONE,
):
    """Creates a single tile of Path."""
    asset_id = ChooseAssetFromTileClass(TileClass.PATH_TILES, map_config, preference)
    return Tile(
        asset_id,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileStone(
    rotation_degrees=0,
    map_config: MapConfig = MapConfig(),
    preference: AssetId = AssetId.NONE,
):
    """Creates a single tile of rocky ground."""
    asset_id = ChooseAssetFromTileClass(TileClass.STONE_TILES, map_config, preference)
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


def GroundTileRocky(rotation_degrees=0):
    """Creates a single tile of rocky ground."""
    return GroundTileStone(rotation_degrees, preference=AssetId.GROUND_TILE_ROCKY)


def GroundTileStones(rotation_degrees=0):
    """Creates a single tile of ground with stones."""
    return GroundTileStone(rotation_degrees, preference=AssetId.GROUND_TILE_STONES)


def GroundTileTreeBrown(rotation_degrees=0):
    """Creates a single tile of ground with a brown tree."""
    return GroundTileTree(rotation_degrees, preference=AssetId.GROUND_TILE_TREE_BROWN)


def GroundTileTrees(rotation_degrees=0):
    """Creates a single tile of ground with trees."""
    return GroundTileTree(rotation_degrees, preference=AssetId.GROUND_TILE_TREES)


def GroundTileRockySnow(rotation_degrees=0):
    """Creates a single tile of rocky ground."""
    tile = GroundTileStone(rotation_degrees)
    return SnowifyTile(tile)


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


def TreeAssetIds(map_config: MapConfig = MapConfig()):
    """Returns a list of tree asset ids."""
    return [AssetId[name] for name in map_config.tree_tiles]


def GroundTileTree(
    rotation_degrees=0,
    map_config: MapConfig = MapConfig(),
    preference: AssetId = AssetId.NONE,
):
    """Creates a single tile of ground with a tree on it."""
    asset_id = ChooseAssetFromTileClass(TileClass.TREE_TILES, map_config, preference)
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


def NatureAssetIds(map_config: MapConfig = MapConfig()):
    asset_names = (
        map_config.tree_tiles + map_config.stone_tiles + map_config.foliage_tiles
    )
    return [AssetId[name] for name in asset_names]


def RandomNatureTile(rotation_degrees=0, map_config: MapConfig = MapConfig()):
    """Creates a single tile of nature. Nature tiles are trees, rocks, foliage, etc."""
    return Tile(
        random.choice(NatureAssetIds(map_config=map_config)),
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
        return AssetId.NONE


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


def UrbanHouseTile(
    rotation_degrees=0,
    map_config: MapConfig = MapConfig(),
    preference: AssetId = AssetId.NONE,
):
    """Creates a random house tile (like GroundTileHouse type=HouseType.RANDOM, but with a distribution meant for cities."""
    asset_id = ChooseAssetFromTileClass(
        TileClass.URBAN_HOUSE_TILES, map_config, preference
    )
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


def GroundTileStreetLight(
    rotation_degrees=0,
    map_config: MapConfig = MapConfig(),
    preference: AssetId = AssetId.NONE,
):
    """Creates a single tile of ground with a street light."""
    asset_id = ChooseAssetFromTileClass(
        TileClass.STREETLIGHT_TILES, map_config, preference
    )
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


def GroundTileStreetLightFoilage(rotation_degrees=0):
    """Creates a single tile of ground with a street light and some bushes/rocks around it."""
    return Tile(
        AssetId.GROUND_TILE_STREETLIGHT_FOILAGE,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileStreetLightBig(rotation_degrees=0):
    """Creates a single tile of ground with a tall street light."""
    return Tile(
        AssetId.STREETLIGHT_BIG,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileStreetLightBushes(rotation_degrees=0):
    """Creates a single tile of ground with a street light and some bushes around it."""
    return Tile(
        AssetId.STREETLIGHT_BUSHES,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileStreetLightRocks(rotation_degrees=0):
    """Creates a single tile of ground with a street light and some rocks around it."""
    return Tile(
        AssetId.STREETLIGHT_ROCKS,
        HexCell(
            HecsCoord.from_offset(0, 0),
            HexBoundary(0x3F),
            LayerToHeight(0),  # Height (float)
            0,  # Z-Layer (int)
        ),
        rotation_degrees,
    )


def GroundTileStreetLightWide(rotation_degrees=0):
    """Creates a single tile of ground with a street light and some rocks around it."""
    return Tile(
        AssetId.STREETLIGHT_WIDE,
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


def AddCardCovers(prop_update, follower=None):
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
            # Make the follower border blue.
            new_prop_info = dataclasses.replace(
                prop_item.prop_info, border_color_follower=Color(0, 0, 1, 1)
            )
            prop_item = dataclasses.replace(prop_item, prop_info=new_prop_info)
        new_card_init = dataclasses.replace(prop_item.card_init, hidden=hidden)
        props.append(dataclasses.replace(prop_item, card_init=new_card_init))
    return dataclasses.replace(prop_update, props=props)
