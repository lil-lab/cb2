# File: data_classes
# ------------------
# Defines classes to store preprocessed data in.

from enum import Enum

from server.assets import AssetId


class ActionEnums(Enum):
    MF = 0
    MB = 1
    TR = 2
    TL = 3
    DONE = 4
    PAD = 5
    END_TURN = 6


class MapProperty(Enum):
    """
    Enumerator representing the various properties an asset in CB2 could have.
    """

    # Padding index
    PAD = 0

    # Rotations
    ROT_0 = 1
    ROT_60 = 2
    ROT_120 = 3
    ROT_180 = 4
    ROT_240 = 5
    ROT_300 = 6

    # Layers
    LAYER0 = 7
    LAYER1 = 8
    LAYER2 = 9

    # Tile contents
    GROUND_TILE = 10
    ROCKY = 11
    STONES = 12
    TREES = 13
    HOUSES = 14
    STREETLIGHT = 15
    PATH = 16
    WATER = 17
    MOUNTAIN = 18
    RAMP = 19

    # Stone types
    STONE_TYPE_0 = 20
    STONE_TYPE_1 = 21
    STONE_TYPE_2 = 22
    STONE_TYPE_3 = 23

    # Tree types
    TREE_DEFAULT = 24
    TREE_BROWN = 25
    TREE_DARKGREEN = 26
    TREE_SOLIDBROWN = 27
    TREE_TREES = 28
    TREE_TREES_2 = 29
    TREE_FOREST = 30

    # House properties
    HOUSE_TRIPLE = 31
    HOUSE_COLOR_DEFAULT = 32
    HOUSE_COLOR_RED = 33
    HOUSE_COLOR_BLUE = 34
    HOUSE_COLOR_GREEN = 35
    HOUSE_COLOR_ORANGE = 36
    HOUSE_COLOR_PINK = 37
    HOUSE_COLOR_YELLOW = 38

    # Snow
    SNOW = 39


asset_to_properties = {
    # Ground tile props
    AssetId.GROUND_TILE.value: [MapProperty["GROUND_TILE"]],
    # Rocky tile props
    AssetId.GROUND_TILE_ROCKY.value: [MapProperty["ROCKY"]],
    # Stone tile props
    AssetId.GROUND_TILE_STONES.value: [
        MapProperty["STONES"],
        MapProperty["STONE_TYPE_0"],
    ],
    AssetId.GROUND_TILE_STONES_GREENBUSH.value: [
        MapProperty["STONES"],
        MapProperty["STONE_TYPE_1"],
    ],
    AssetId.GROUND_TILE_STONES_BROWNBUSH.value: [
        MapProperty["STONES"],
        MapProperty["STONE_TYPE_2"],
    ],
    AssetId.GROUND_TILE_STONES_GREYBUSH.value: [
        MapProperty["STONES"],
        MapProperty["STONE_TYPE_3"],
    ],
    # Tree tile props
    AssetId.GROUND_TILE_TREE.value: [MapProperty["TREES"], MapProperty["TREE_DEFAULT"]],
    AssetId.GROUND_TILE_TREE_BROWN.value: [
        MapProperty["TREES"],
        MapProperty["TREE_BROWN"],
    ],
    AssetId.GROUND_TILE_TREE_SNOW.value: [
        MapProperty["TREES"],
        MapProperty["TREE_DEFAULT"],
        MapProperty["SNOW"],
    ],
    AssetId.GROUND_TILE_TREE_DARKGREEN.value: [
        MapProperty["TREES"],
        MapProperty["TREE_DARKGREEN"],
    ],
    AssetId.GROUND_TILE_TREE_SOLIDBROWN.value: [
        MapProperty["TREES"],
        MapProperty["TREE_SOLIDBROWN"],
    ],
    AssetId.GROUND_TILE_TREES.value: [MapProperty["TREES"], MapProperty["TREE_TREES"]],
    AssetId.GROUND_TILE_TREES_2.value: [
        MapProperty["TREES"],
        MapProperty["TREE_TREES_2"],
    ],
    AssetId.GROUND_TILE_FOREST.value: [
        MapProperty["TREES"],
        MapProperty["TREE_FOREST"],
    ],
    # House tile props
    AssetId.GROUND_TILE_HOUSE.value: [
        MapProperty["HOUSES"],
        MapProperty["HOUSE_COLOR_DEFAULT"],
    ],
    AssetId.GROUND_TILE_HOUSE_RED.value: [
        MapProperty["HOUSES"],
        MapProperty["HOUSE_COLOR_RED"],
    ],
    AssetId.GROUND_TILE_HOUSE_BLUE.value: [
        MapProperty["HOUSES"],
        MapProperty["HOUSE_COLOR_BLUE"],
    ],
    AssetId.GROUND_TILE_HOUSE_GREEN.value: [
        MapProperty["HOUSES"],
        MapProperty["HOUSE_COLOR_GREEN"],
    ],
    AssetId.GROUND_TILE_HOUSE_ORANGE.value: [
        MapProperty["HOUSES"],
        MapProperty["HOUSE_COLOR_ORANGE"],
    ],
    AssetId.GROUND_TILE_HOUSE_PINK.value: [
        MapProperty["HOUSES"],
        MapProperty["HOUSE_COLOR_PINK"],
    ],
    AssetId.GROUND_TILE_HOUSE_YELLOW.value: [
        MapProperty["HOUSES"],
        MapProperty["HOUSE_COLOR_YELLOW"],
    ],
    # Triple house tile props
    AssetId.GROUND_TILE_HOUSE_TRIPLE.value: [
        MapProperty["HOUSES"],
        MapProperty["HOUSE_TRIPLE"],
        MapProperty["HOUSE_COLOR_DEFAULT"],
    ],
    AssetId.GROUND_TILE_HOUSE_TRIPLE_RED.value: [
        MapProperty["HOUSES"],
        MapProperty["HOUSE_TRIPLE"],
        MapProperty["HOUSE_COLOR_RED"],
    ],
    AssetId.GROUND_TILE_HOUSE_TRIPLE_BLUE.value: [
        MapProperty["HOUSES"],
        MapProperty["HOUSE_TRIPLE"],
        MapProperty["HOUSE_COLOR_BLUE"],
    ],
    # Miscellaneous props
    AssetId.GROUND_TILE_STREETLIGHT.value: [MapProperty["STREETLIGHT"]],
    AssetId.GROUND_TILE_PATH.value: [MapProperty["PATH"]],
    AssetId.WATER_TILE.value: [MapProperty["WATER"]],
    AssetId.MOUNTAIN_TILE.value: [MapProperty["MOUNTAIN"]],
    AssetId.RAMP_TO_MOUNTAIN.value: [MapProperty["RAMP"]],
    # Snowy tile props
    AssetId.SNOWY_GROUND_TILE.value: [MapProperty["GROUND_TILE"], MapProperty["SNOW"]],
    AssetId.SNOWY_GROUND_TILE_TREES_2.value: [
        MapProperty["TREES"],
        MapProperty["TREE_TREES_2"],
        MapProperty["SNOW"],
    ],
    AssetId.SNOWY_GROUND_TILE_ROCKY.value: [MapProperty["ROCKY"], MapProperty["SNOW"]],
    AssetId.SNOWY_GROUND_TILE_STONES.value: [
        MapProperty["STONES"],
        MapProperty["STONE_TYPE_0"],
        MapProperty["SNOW"],
    ],
    AssetId.SNOWY_MOUNTAIN_TILE.value: [MapProperty["MOUNTAIN"], MapProperty["SNOW"]],
    AssetId.SNOWY_RAMP_TO_MOUNTAIN.value: [MapProperty["RAMP"], MapProperty["SNOW"]],
    AssetId.MOUNTAIN_TILE_TREE.value: [
        MapProperty["TREES"],
        MapProperty["TREE_DEFAULT"],
    ],
    AssetId.SNOWY_MOUNTAIN_TILE_TREE.value: [
        MapProperty["TREES"],
        MapProperty["TREE_DEFAULT"],
        MapProperty["SNOW"],
    ],
}


class DynamicProperty(Enum):
    """
    Enumerator representing the various properties an asset in CB2 could have.
    """

    # Tile contents
    CARD = 40
    FOLLOWER = 41
    LEADER = 42

    # Card properties
    SELECTED = 43
    UNSELECTED = 44

    # Card shapes
    PLUS = 45
    TORUS = 46
    HEART = 47
    DIAMOND = 48
    SQUARE = 49
    STAR = 50
    TRIANGLE = 51

    # Card color
    BLACK = 52
    BLUE = 53
    GREEN = 54
    ORANGE = 55
    PINK = 56
    RED = 57
    YELLOW = 58

    # Card count
    COUNT_1 = 59
    COUNT_2 = 60
    COUNT_3 = 61

    # Agent rotations
    FOLLOWER_ROT_0 = 62
    FOLLOWER_ROT_60 = 63
    FOLLOWER_ROT_120 = 64
    FOLLOWER_ROT_180 = 65
    FOLLOWER_ROT_240 = 66
    FOLLOWER_ROT_300 = 67

    LEADER_ROT_0 = 68
    LEADER_ROT_60 = 69
    LEADER_ROT_120 = 70
    LEADER_ROT_180 = 71
    LEADER_ROT_240 = 72
    LEADER_ROT_300 = 73


class StaticMap:
    """
    A wrapper for a dictionary mapping from coordinates within the
    map (in offset format) to a list of indices representing various
    properties of the assets held in each tile.
    """

    def __init__(self, recent_map):
        self.coord_to_props = {}

        # Iterate over each tile
        for tile in recent_map.tiles:
            if tile is None:
                continue

            # Extract offset coordinates of tile
            offset_coord = tile.cell.coord.to_offset_coordinates()[::-1]
            properties = self.get_property_list(tile)
            self.coord_to_props[offset_coord] = properties

    def get_property_list(self, tile):
        props = []

        # Basic properties
        rot_prop = MapProperty[f"ROT_{int(tile.rotation_degrees % 360)}"]
        layer_prop = MapProperty[f"LAYER{tile.cell.layer}"]
        props.extend([rot_prop, layer_prop])

        # Asset id processing
        asset_id = tile.asset_id
        asset_props = asset_to_properties[asset_id]
        props.extend(asset_props)

        return props


class DynamicMap:
    """
    A wrapper for a dictionary mapping from coordinates within the
    map (in offset format) to a list of indices representing various
    properties of the assets held in each tile.
    """

    def __init__(self, cards, f_loc, f_ang, l_loc=None, l_ang=None):
        self.coord_to_props = {}

        self.add_agent(f_loc, f_ang, "FOLLOWER")
        self.unpack_cards(cards)
        self.add_agent(l_loc, l_ang, "LEADER")

    def get_follower_loc(self):
        for coord, props in self.coord_to_props.items():
            if DynamicProperty["FOLLOWER"] in props:
                return coord
        assert False, "There must be a follower property in DynamicMap"

    def get_follower_rot(self):
        for coord, props in self.coord_to_props.items():
            if DynamicProperty["FOLLOWER"] in props:
                for i in range(6):
                    if DynamicProperty[f"FOLLOWER_ROT_{i * 60}"] in props:
                        return i * 60
        assert False, "There must be a follower property in DynamicMap"

    def card_at(self, pos):
        # Return if there is a card at a given location
        if pos not in self.coord_to_props:
            return False
        else:
            props = self.coord_to_props[pos]
            return DynamicProperty["CARD"] in props

    def add_agent(self, loc, ang, agent_type):
        if loc is None:
            return

        agent_coord = loc.to_offset_coordinates()[::-1]
        props = [
            DynamicProperty[agent_type],
            DynamicProperty[f"{agent_type}_ROT_{int(ang)}"],
        ]

        if agent_coord not in self.coord_to_props:
            self.coord_to_props[agent_coord] = props
        else:
            # Only called for leader
            self.coord_to_props[agent_coord].extend(props)

    def unpack_cards(self, cards):
        for card in cards:
            props = [DynamicProperty["CARD"]]
            card_coord = card.prop_info.location.to_offset_coordinates()[::-1]

            if card_coord in self.coord_to_props:
                # If position occupied by the follower, add limited information
                selectedness = "SELECTED" if card.card_init.selected else "UNSELECTED"
                props.append(DynamicProperty[selectedness])
                self.coord_to_props[card_coord].extend(props)
            elif not card.card_init.selected:
                props.append(DynamicProperty["UNSELECTED"])
                self.coord_to_props[card_coord] = props
            else:
                props.append(DynamicProperty["SELECTED"])

                # Add shape
                shape = card.card_init.shape
                props.append(DynamicProperty[shape.name])

                # Add color
                color = card.card_init.color
                props.append(DynamicProperty[color.name])

                # Add count
                count = card.card_init.count
                props.append(DynamicProperty[f"COUNT_{count}"])

                self.coord_to_props[card_coord] = props
