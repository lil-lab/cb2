from assets import AssetId
from messages.map_update import MapUpdate
from messages.bug_report import BugReport
from messages.prop import PropType, GenericPropInfo, CardConfig, Prop
from card import Shape, Color
from hex import HexBoundary, Edges

import math
import pygame
import sys

SCREEN_SIZE = 800
SCALE = 5
BORDER = 0

pygame.font.init()
GAME_FONT = pygame.font.SysFont('Helvetica', 30)

def wait_for_key():
    """ Waits for a key to be pressed and then exits the program. """
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                return

def PygameColorFromCardColor(card_color):
    """ Matches an instance of card.Color to a pygame color object."""
    if card_color == Color.BLACK:
        return pygame.Color("black")
    elif card_color == Color.BLUE:
        return pygame.Color("blue")
    elif card_color == Color.GREEN:
        return pygame.Color("green")
    elif card_color == Color.ORANGE:
        return pygame.Color("orange")
    elif card_color == Color.PINK:
        return pygame.Color("pink")
    elif card_color == Color.RED:
        return pygame.Color("red")
    elif card_color == Color.YELLOW:
        return pygame.Color("yellow")

def asset_id_to_color(asset_id):
    """ Matches each asset id (in AssetId) with a unique color.

        GROUND_TILE -> Light Green
        GROUND_TILE_ROCKY -> Grey-Blue
        GROUND_TILE_STONES -> Grey-Blue
        GROUND_TILE_TREES -> Green
        GROUND_TILE_TREES_2 -> Green
        GROUND_TILE_FOREST -> Dark Green
        GROUND_TILE_HOUSE -> Red
        GROUND_TILE_STREETLIGHT -> Yellow
        MOUNTAIN_TILE -> Brown
        RAMP_TO_MOUNTAIN -> Tan
    
        Defaults to white if unknown.
    """
    if asset_id == AssetId.GROUND_TILE:
        return pygame.Color("lightgreen")
    elif asset_id == AssetId.GROUND_TILE_ROCKY:
        return pygame.Color("grey")
    elif asset_id == AssetId.GROUND_TILE_STONES:
        return pygame.Color("grey")
    elif asset_id == AssetId.GROUND_TILE_TREES:
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_TREES_2:
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_FOREST:
        return pygame.Color("darkgreen")
    elif asset_id == AssetId.GROUND_TILE_HOUSE:
        return pygame.Color("red")
    elif asset_id == AssetId.GROUND_TILE_STREETLIGHT:
        return pygame.Color("yellow")
    elif asset_id == AssetId.MOUNTAIN_TILE:
        return pygame.Color("brown")
    elif asset_id == AssetId.RAMP_TO_MOUNTAIN:
        return pygame.Color("tan4")
    elif asset_id == AssetId.GROUND_TILE_PATH:
        return pygame.Color("tan")
    elif asset_id == AssetId.EMPTY_TILE:
        return pygame.Color("black")
    elif asset_id == AssetId.WATER_TILE:
        return pygame.Color("blue")
    else:
        print("Unknown asset ID encountered: " + str(asset_id))
        return pygame.Color("white")

def asset_id_to_text(asset_id):
    return str(asset_id)

def get_hexagon_vertices(x, y, width, height, rotation):
    """ Gets the vertices of a hexagon.

        x, y: The center of the hexagon.
        width, height: The width and height of the hexagon.
        rotation: The rotation of the hexagon.
    """
    vertices = []

    # Get the vertices of the hexagon.
    for i in range(6):
        # Get the angle of the vertex.
        angle = i * 60 - 90

        # Get the x and y coordinates of the vertex.
        x_vertex = x + 0.5 * width * math.cos(math.radians(angle))
        y_vertex = y + 0.5 * height * math.sin(math.radians(angle))

        # Add the vertex to the list of vertices.
        vertices.append((x_vertex, y_vertex))

    return vertices
    

def draw_hexagon(screen, x, y, width, height, color, rotation, boundary):
    """ Draws a hexagon to the screen.

        x, y: The center of the hexagon.
        width, height: The width and height of the hexagon.
        color: The color of the hexagon.
        rotation: The rotation of the hexagon.
        boundary: which walls are blocked.
    """
    # Get the vertices of the hexagon.
    vertices = get_hexagon_vertices(x, y, width, height, rotation)

    # Draw the hexagon with a white fill and 1px black border.
    pygame.draw.polygon(screen, color, vertices, 0)

    line_width = 4
    line_color = pygame.Color("black")
    if boundary.get_edge(Edges.UPPER_RIGHT):
        pygame.draw.line(screen, line_color, vertices[0], vertices[1], line_width)
    
    if boundary.get_edge(Edges.RIGHT):
        pygame.draw.line(screen, line_color, vertices[1], vertices[2], line_width)
        
    if boundary.get_edge(Edges.LOWER_RIGHT):
        pygame.draw.line(screen, line_color, vertices[2], vertices[3], line_width)

    if boundary.get_edge(Edges.LOWER_LEFT):
        pygame.draw.line(screen, line_color, vertices[3], vertices[4], line_width)
    
    if boundary.get_edge(Edges.LEFT):
        pygame.draw.line(screen, line_color, vertices[4], vertices[5], line_width)
    
    if boundary.get_edge(Edges.UPPER_LEFT):
        pygame.draw.line(screen, line_color, vertices[5], vertices[0], line_width)

def draw_card(screen, x, y, width, height, card_info):
    """ Draws a card to the screen.

        screen: A pygame screen to draw to.
        x, y: The center of the card.
        width, height: The width and height of the card.
        card_info: Card info, including shape, color, and more.
    """
    # Draw the card as a rectangle with a white fill and 1px black border.
    pygame.draw.rect(screen, pygame.Color("white"), (x - width / 2, y - height / 2, width, height), 0)
    outline_color = pygame.Color("blue") if card_info.selected else pygame.Color("black")
    outline_radius = 5 if card_info.selected else 1
    pygame.draw.rect(screen, outline_color, (x - width / 2, y - height / 2, width, height), outline_radius)

    for i in range(card_info.count):
        color = PygameColorFromCardColor(card_info.color)
        offset = - (height / 5) * ((card_info.count) / 2) + (height / 5) * i
        draw_shape(screen, x, y + offset, card_info.shape, color)

def draw_shape(screen, x, y, shape, color):
    """ Draws a shape to the screen.

        screen: A pygame screen to draw to.
        x, y: The center of the shape.
        shape: The shape to draw.
    """
    (x, y) = (int(x), int(y))
    if shape == Shape.PLUS:
        pygame.draw.line(screen, color, (x - 2, y), (x + 2, y), 1)
        pygame.draw.line(screen, color, (x, y - 2), (x, y + 2), 1)
    elif shape == Shape.TORUS:
        pygame.draw.circle(screen, color, (x, y), 2, 0)
    elif shape == Shape.HEART:
        pygame.draw.polygon(screen, color, ((x, y + 3), (x - 4, y - 1), (x - 2, y - 3), (x, y - 1), (x + 2, y - 3), (x + 4, y - 1)), 0)
    elif shape == Shape.DIAMOND:
        pygame.draw.polygon(screen, color, ((x, y + 3), (x - 3, y), (x, y - 3), (x + 3, y)), 0)
    elif shape == Shape.SQUARE:
        pygame.draw.rect(screen, color, (x - 2.5, y - 2.5, 5, 5), 0)
    elif shape == Shape.STAR:
        pygame.draw.polygon(screen, color, ((x - 3, y - 1), (x + 3, y - 1), (x, y + 5)), 0)
        pygame.draw.polygon(screen, color, ((x - 3, y + 3), (x + 3, y + 3), (x, y - 3)), 0)
    elif shape == Shape.TRIANGLE:
        vertices = [(x, y - 2.5), (x - 2.5, y + 2.5), (x + 2.5, y + 2.5)]
        pygame.draw.polygon(screen, color, vertices, 0)

def draw_map_and_wait(map_update): 
    display = GameDisplay(SCREEN_SIZE)

    display.set_map(map_update)
    display.draw()

    pygame.display.flip()
    wait_for_key()

class GameDisplay(object):
    """ A class that displays the game state to the screen. """
    def __init__(self, screen_size):
        self._screen_size = screen_size
        self._cell_width = self._cell_height = 0
        self._map = None
        self._game_state = None
        # Initialize pygame.
        pygame.init()
        # Create the screen
        self._screen = pygame.display.set_mode((self._screen_size,
                                                self._screen_size))
        pygame.display.set_caption("Game Visualizer")
    
    def screen(self):
        return self._screen
    
    def set_map(self, map):
        self._map = map
        screen_size = self._screen_size - 2 * BORDER
        self._cell_height = (screen_size / self._map.rows)
        self._cell_width = (screen_size / self._map.cols)
        # Determine which cell dimension is smaller. Recalculate the other dimension
        # to maintain the aspect ratio.
        if self._cell_width > self._cell_height:
            self._cell_width = self._cell_height * (1/1.5) * math.sqrt(3)
        else:
            self._cell_height = self._cell_width * 1.5 / math.sqrt(3)

    def set_game_state(self, game_state):
        self._game_state = game_state

    def transform_to_screen_coords(self, coords):
        """ Transforms the given map x, y coordinates to screen coordinates.

            x, y: A coordinate in map space.
        """
        (x, y) = coords
        x_scale = self._cell_width * 0.9
        y_scale = self._cell_height * 0.9
        x = (x + 1) * x_scale
        x += BORDER
        y = (y + 1) * y_scale
        y += BORDER
        return (x, y)
    
    def visualize_map(self):
        if self._map is None:
            return

        # Draw the map
        for tile in self._map.tiles:
            # Get the tile color.
            asset_id = tile.asset_id
            color = asset_id_to_color(asset_id)

            # Get the center of the hexagonal cell.
            cell = tile.cell
            (center_x, center_y) = self.transform_to_screen_coords(cell.coord.cartesian())

            # Get the boundary of the cell.
            boundary = cell.boundary

            # Draw the cell.
            draw_hexagon(self._screen, center_x, center_y, self._cell_width,
                         self._cell_height, color, tile.rotation_degrees,
                         boundary)

        # Draw card props.
        for prop in self._map.props:
            if prop.prop_type != PropType.CARD:
                continue
            # Get the card location.
            loc = prop.prop_info.location
            (center_x, center_y) = self.transform_to_screen_coords(loc.cartesian())
            draw_card(self._screen, center_x, center_y,
                      self._cell_width / 2, self._cell_height * 0.7,
                      prop.card_init)


    def visualize_actor(self, actor_index):
        actor = self._game_state.actors[actor_index]
        (x, y) = self.transform_to_screen_coords(actor.location.cartesian())
        pygame.draw.circle(self._screen, pygame.Color("red"), (x, y), 10)
        heading = actor.rotation_degrees - 60
        pointer_length = 20
        pygame.draw.line(self._screen, pygame.Color("red"), (x, y),
                    (x + pointer_length * math.cos(math.radians(heading)),
                    y + pointer_length * math.sin(math.radians(heading))))
        actor_id = actor.actor_id
        text = GAME_FONT.render(str(actor_id), False, pygame.Color("black"))
        self._screen.blit(text, (x - text.get_width() / 2, y - text.get_height() / 2))
    
    def visualize_game_state(self):
        if self._map is None or self._game_state is None:
            return
        for i in range(self._game_state.population):
            self.visualize_actor(i)

    def draw(self):
        # Fill the screen with white
        self._screen.fill((255,255,255))

        self.visualize_map()
        self.visualize_game_state()

def main():
    """ Reads a JSON bug report from a file provided on the command line and displays the map to the user. """
    # Check that the correct number of arguments were provided.
    if len(sys.argv) != 2:
        print("Usage: python visualize.py <bug_report.json>")
        quit()

    # Read file contents and parse them into a JSON MapUpdate.
    with open(sys.argv[1], "r") as file:
        bug_report = BugReport.from_json(file.read())
        draw_map_and_wait(bug_report.map_update)

if __name__ == "__main__":
    main()
