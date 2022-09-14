from enum import IntEnum

class AssetId(IntEnum):
    PLAYER = 0
    PLAYER_WITH_CAM = 1
    FOLLOWER_BOT = 2
    GROUND_TILE = 3
    GROUND_TILE_ROCKY = 4
    GROUND_TILE_STONES = 5
    GROUND_TILE_STONES_GREENBUSH = 6
    GROUND_TILE_STONES_BROWNBUSH = 7
    GROUND_TILE_STONES_GREYBUSH = 8
    GROUND_TILE_TREE = 9
    GROUND_TILE_TREE_BROWN = 10
    GROUND_TILE_TREE_SNOW = 11
    GROUND_TILE_TREE_DARKGREEN = 12
    GROUND_TILE_TREE_SOLIDBROWN = 13
    GROUND_TILE_TREES = 14
    GROUND_TILE_TREES_2 = 15
    GROUND_TILE_FOREST = 16
    GROUND_TILE_HOUSE = 17
    GROUND_TILE_HOUSE_RED = 18
    GROUND_TILE_HOUSE_BLUE = 19
    GROUND_TILE_HOUSE_GREEN = 20
    GROUND_TILE_HOUSE_ORANGE = 21
    GROUND_TILE_HOUSE_PINK = 22
    GROUND_TILE_HOUSE_YELLOW = 23
    GROUND_TILE_HOUSE_TRIPLE = 24
    GROUND_TILE_HOUSE_TRIPLE_RED = 25
    GROUND_TILE_HOUSE_TRIPLE_BLUE = 26
    GROUND_TILE_STREETLIGHT = 27
    GROUND_TILE_PATH = 28
    WATER_TILE = 29
    MOUNTAIN_TILE = 30
    RAMP_TO_MOUNTAIN = 31
    SNOWY_GROUND_TILE = 32
    SNOWY_GROUND_TILE_TREES_2 = 33
    SNOWY_GROUND_TILE_ROCKY = 34
    SNOWY_GROUND_TILE_STONES = 35
    SNOWY_MOUNTAIN_TILE = 36
    SNOWY_RAMP_TO_MOUNTAIN = 37
    CARD_BASE_4 = 38
    CARD_BASE_5 = 39
    CARD_BASE_6 = 40
    MOUNTAIN_TILE_TREE = 41
    SNOWY_MOUNTAIN_TILE_TREE = 42
    EMPTY_TILE = 100 # Used for map gen, should never appear in network protocol.
    NONE = 101 # Invalid value. Used for padding/masking unknown values.
    MAX = 102 # Maximum possible value. Subject to change.

def TreeAssets():
    """ Returns a list of snow-themed assets. """
    return [AssetId.GROUND_TILE_TREE, AssetId.GROUND_TILE_TREE_BROWN, AssetId.GROUND_TILE_TREES_2, AssetId.GROUND_TILE_TREE_DARKGREEN, AssetId.GROUND_TILE_TREE_SOLIDBROWN]

def SnowifyAssetId(asset_id):
    if asset_id == AssetId.GROUND_TILE:
        return AssetId.SNOWY_GROUND_TILE
    elif asset_id == AssetId.GROUND_TILE_ROCKY:
        return AssetId.SNOWY_GROUND_TILE_ROCKY
    elif asset_id == AssetId.GROUND_TILE_STONES:
        return AssetId.SNOWY_GROUND_TILE_STONES
    elif asset_id == AssetId.GROUND_TILE_TREE:
        return AssetId.GROUND_TILE_TREE_SNOW
    elif asset_id == AssetId.MOUNTAIN_TILE:
        return AssetId.SNOWY_MOUNTAIN_TILE
    elif asset_id == AssetId.RAMP_TO_MOUNTAIN:
        return AssetId.SNOWY_RAMP_TO_MOUNTAIN
    elif asset_id == AssetId.GROUND_TILE_TREES_2:
        return AssetId.SNOWY_GROUND_TILE_TREES_2
    elif asset_id == AssetId.MOUNTAIN_TILE_TREE:
        return AssetId.SNOWY_MOUNTAIN_TILE_TREE
    elif asset_id == AssetId.GROUND_TILE_TREE_BROWN:
        return asset_id
    elif asset_id in TreeAssets():
        return AssetId.GROUND_TILE_TREE_SNOW
    else:
        return asset_id

def is_snowy(asset_id):
    return asset_id in [AssetId.SNOWY_GROUND_TILE, AssetId.SNOWY_GROUND_TILE_TREES_2, AssetId.SNOWY_GROUND_TILE_ROCKY, AssetId.SNOWY_GROUND_TILE_STONES, AssetId.SNOWY_MOUNTAIN_TILE, AssetId.SNOWY_RAMP_TO_MOUNTAIN, AssetId.GROUND_TILE_TREE_SNOW, AssetId.SNOWY_MOUNTAIN_TILE_TREE]

def SnowAssets():
    """ Snowy tiles. """
    return [AssetId.SNOWY_GROUND_TILE, AssetId.SNOWY_GROUND_TILE_TREES_2, AssetId.SNOWY_GROUND_TILE_ROCKY, AssetId.SNOWY_GROUND_TILE_STONES, AssetId.GROUND_TILE_TREE_SNOW]

def TreeFrequencies():
    """ Returns a list of len(TreeAssets()) with the "proper" frequency of each asset. """
    return [0.3, 0.1, 0.15, 0.2, 0.2]

def NatureAssets():
    """ Trees, stones, or any other sort of blocking tile that would fit in a forest. """
    return TreeAssets() + [AssetId.GROUND_TILE_STONES, AssetId.GROUND_TILE_ROCKY, AssetId.GROUND_TILE_STONES_BROWNBUSH, AssetId.GROUND_TILE_STONES_GREYBUSH, AssetId.GROUND_TILE_STONES_GREENBUSH]