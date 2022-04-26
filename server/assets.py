from enum import IntEnum

class AssetId(IntEnum):
    PLAYER = 0
    PLAYER_WITH_CAM = 1
    FOLLOWER_BOT = 2
    GROUND_TILE = 3
    GROUND_TILE_ROCKY = 4
    GROUND_TILE_STONES = 5
    GROUND_TILE_TREE = 6
    GROUND_TILE_TREE_BROWN = 7
    GROUND_TILE_TREE_SNOW = 8
    GROUND_TILE_TREES = 9
    GROUND_TILE_TREES_2 = 10
    GROUND_TILE_FOREST = 11
    GROUND_TILE_HOUSE = 12
    GROUND_TILE_HOUSE_RED= 13
    GROUND_TILE_HOUSE_BLUE = 14
    GROUND_TILE_HOUSE_GREEN = 15
    GROUND_TILE_HOUSE_ORANGE = 16
    GROUND_TILE_HOUSE_PINK = 17
    GROUND_TILE_HOUSE_YELLOW = 18
    GROUND_TILE_HOUSE_TRIPLE = 19
    GROUND_TILE_HOUSE_TRIPLE_RED = 20
    GROUND_TILE_HOUSE_TRIPLE_BLUE = 21
    GROUND_TILE_STREETLIGHT = 22
    GROUND_TILE_PATH = 23
    WATER_TILE = 24
    MOUNTAIN_TILE = 25
    RAMP_TO_MOUNTAIN = 26
    SNOWY_GROUND_TILE = 27
    SNOWY_GROUND_TILE_TREES_2 = 28
    SNOWY_GROUND_TILE_ROCKY = 29
    SNOWY_GROUND_TILE_STONES = 30
    SNOWY_MOUNTAIN_TILE = 31
    SNOWY_RAMP_TO_MOUNTAIN = 32
    CARD_BASE_4 = 33
    CARD_BASE_5 = 34
    CARD_BASE_6 = 35
    EMPTY_TILE = 100 # Used for map gen, should never appear in network protocol.

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
    else:
        return asset_id

def TreeAssets():
    """ Returns a list of snow-themed assets. """
    return [AssetId.GROUND_TILE_TREE, AssetId.GROUND_TILE_TREE_BROWN, AssetId.GROUND_TILE_TREE_SNOW, AssetId.GROUND_TILE_TREES_2]

def TreeFrequencies():
    """ Returns a list of len(TreeAssets()) with the "proper" frequency of each asset. """
    return [0.7, 0.1, 0.05, 0.15]

def NatureAssets():
    """ Trees, stones, or any other sort of blocking tile that would fit in a forest. """
    return TreeAssets() + [AssetId.GROUND_TILE_STONES, AssetId.GROUND_TILE_ROCKY]