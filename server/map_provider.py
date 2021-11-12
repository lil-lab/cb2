""" This utility streams a hardcoded map to clients. """
from messages.map_update import MapUpdate, Tile
from assets import AssetId
from hex import HecsCoord, HexCell, HexBoundary
from card import Card, Shape, Color
import random

MAP_WIDTH = 12
MAP_HEIGHT = 24


def HardcodedMap():
    """ Creates a map of Tile objects, each with HECS coordinates and locations."""
    map = []
    for r in range(0, MAP_HEIGHT):
        row = []
        for c in range(0, MAP_WIDTH):
            tile = GroundTile(r, c)
            row.append(tile)
        map.append(row)

    # Single ramp at start
    map[2][2] = RampToMountain(2, 2)
    map[2][3] = MountainTile(2, 3)
    map[2][4] = MountainTile(2, 4)
    map[2][5] = MountainTile(2, 5)
    map[2][6] = RampToMountain(2, 6, 180)
    map[3][5] = RampToMountain(3, 5, 240)

    # Add trees
    map[5][5] = GroundTileTrees(5, 5)
    map[5][7] = GroundTileTrees(5, 7, 60)
    map[6][5] = GroundTileTrees(6, 5, 120)
    map[6][7] = GroundTileTrees(6, 7, 180)

    # Add rocks
    map[4][4] = GroundTileRocky(4, 4, 60)
    map[4][8] = GroundTileRocky(4, 8, 180)
    map[2][9] = GroundTileRocky(2, 9, 240)
    map[5][8] = GroundTileRocky(5, 8, 300)
    map[6][4] = GroundTileRocky(6, 4)

    # Add a house.
    map[7][7] = GroundTileHouse(7, 7)

    # Add mountains.
    map[8][5] = MountainTile(8, 5)
    map[8][6] = MountainTile(8, 6)
    map[8][7] = MountainTile(8, 7)
    map[8][8] = MountainTile(8, 8)
    map[9][5] = MountainTile(9, 5)
    map[9][6] = MountainTile(9, 6)
    map[9][7] = RampToMountain(9, 7, 180)

    # Add a street light.
    map[5][3] = GroundTileStreetLight(5, 3)

    # Add ramps to mountain.
    map[8][4] = RampToMountain(8, 4)
    map[9][4] = RampToMountain(9, 4)

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
        2: 0.325,
    }
    if layer not in layer_to_height:
        return layer_to_height[0]

    return layer_to_height[layer]


def GroundTile(r, c, rotation_degrees=0):
    """ Creates a single tile of ground."""
    return Tile(
        AssetId.GROUND_TILE,
        HexCell(HecsCoord.from_offset(r, c), HexBoundary(0),
                LayerToHeight(0),  # Height (float)
                0,  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileRocky(r, c, rotation_degrees=0):
    """ Creates a single tile of rocky ground."""
    return Tile(
        AssetId.GROUND_TILE_ROCKY,
        HexCell(HecsCoord.from_offset(r, c), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileStones(r, c, rotation_degrees=0):
    """ Creates a single tile of ground with stones."""
    return Tile(
        AssetId.GROUND_TILE_STONES,
        HexCell(HecsCoord.from_offset(r, c), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileTrees(r, c, rotation_degrees=0):
    """ Creates a single tile of ground with several trees. """
    return Tile(
        AssetId.GROUND_TILE_TREES,
        HexCell(HecsCoord.from_offset(r, c), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileSingleTree(r, c, rotation_degrees=0):
    """ Creates a single tile of ground with a tree."""
    return Tile(
        AssetId.GROUND_TILE_TREES_2,
        HexCell(HecsCoord.from_offset(r, c), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileForest(r, c, rotation_degrees=0):
    """ Creates a single tile of ground with a forest."""
    return Tile(
        AssetId.GROUND_TILE_FOREST,
        HexCell(HecsCoord.from_offset(r, c), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileHouse(r, c, rotation_degrees=0):
    """ Creates a single tile of ground with a house."""
    return Tile(
        AssetId.GROUND_TILE_HOUSE,
        HexCell(HecsCoord.from_offset(r, c), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def GroundTileStreetLight(r, c, rotation_degrees=0):
    """ Creates a single tile of ground with a street light."""
    return Tile(
        AssetId.GROUND_TILE_STREETLIGHT,
        HexCell(HecsCoord.from_offset(r, c), HexBoundary(0x3F),
                LayerToHeight(0),  # Height (float)
                0  # Z-Layer (int)
                ),
        rotation_degrees
    )


def MountainTile(r, c, rotation_degrees=0):
    """ Creates a single tile of mountain."""
    return Tile(
        AssetId.MOUNTAIN_TILE,
        HexCell(HecsCoord.from_offset(r, c), HexBoundary(0),
                LayerToHeight(2),  # Height (float)
                2  # Z-Layer (int)
                ),
        rotation_degrees
    )


def RampToMountain(r, c, rotation_degrees=0):
    """ Creates a single tile of ramp."""
    return Tile(
        AssetId.RAMP_TO_MOUNTAIN,
        HexCell(HecsCoord.from_offset(r, c), HexBoundary.rotate_cw(HexBoundary(0b101101), rotation_degrees),
                LayerToHeight(1),  # Height (float)
                1  # Z-Layer (int)
                ),
        rotation_degrees
    )


class HardcodedMapProvider(object):
    def __init__(self, id_assigner):
        map = HardcodedMap()
        self._tiles = map.tiles
        self._rows = map.rows
        self._cols = map.cols
        self._cards = []
        self._selected_cards = {}
        self._card_generator = CardGenerator(id_assigner)
        shapes = [Shape.PLUS, Shape.TORUS, Shape.HEART, Shape.DIAMOND,
                  Shape.SQUARE, Shape.STAR, Shape.TRIANGLE]
        colors = [Color.BLACK, Color.BLUE, Color.GREEN,
                  Color.ORANGE, Color.PINK, Color.RED, Color.YELLOW]
        shape_idx = 0
        self._cards.append(self._card_generator.generate_random_card_at(0, 1))
        for i in range(11, 24, 2):
            for j in range(0, 10):
                self._cards.append(self._card_generator.generate_card_at(
                    i, j + 1, shapes[(shape_idx) % len(shapes)], colors[j % len(colors)], j % 3 + 1))
            shape_idx += 1
        self._cards_by_location = {}
        for card in self._cards:
            self._cards_by_location[card.location] = card
        self.add_map_boundaries()
        self.add_layer_boundaries()

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

    def selected_cards(self):
        return self._selected_cards.values()

    def card_by_location(self, location):
        return self._cards_by_location.get(location, None)

    def get_map(self):
        return MapUpdate(self._rows, self._cols, self._tiles, [card.prop() for card in self._cards])