from enum import IntEnum

class AssetId(IntEnum):
    PLAYER = 0
    PLAYER_WITH_CAM = 1
    GROUND_TILE = 2
    GROUND_TILE_ROCKY = 3
    GROUND_TILE_STONES = 4
    GROUND_TILE_TREES = 5
    GROUND_TILE_TREES_2 = 6
    GROUND_TILE_FOREST = 7
    GROUND_TILE_HOUSE = 8
    GROUND_TILE_STREETLIGHT = 9
    GROUND_TILE_PATH = 10
    WATER_TILE = 11
    MOUNTAIN_TILE = 12
    RAMP_TO_MOUNTAIN = 13
    CARD_BASE_1 = 14
    CARD_BASE_2 = 15
    CARD_BASE_3 = 16
    EMPTY_TILE = 17 # Used for map gen, should never appear in network protocol.
