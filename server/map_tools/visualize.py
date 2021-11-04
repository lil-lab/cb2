from assets import AssetId
from messages.map_update import MapUpdate
from hex import HexBoundary, Edges

import math
import pygame
import sys

SCREEN_SIZE = 1000
SCALE = 20

pygame.font.init()
GAME_FONT = pygame.font.SysFont('Helvetica', 30)

def wait_for_key():
    """ Waits for a key to be pressed and then exits the program. """
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()
            if event.type == pygame.KEYDOWN:
                pygame.quit()
                quit()  

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
        return pygame.Color("tan")
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
        # Initialize pygame.
        pygame.init()
        # Create the screen
        self._screen = pygame.display.set_mode((self._screen_size,
                                                self._screen_size))
        pygame.display.set_caption("Game Visualizer")
    
    def set_map(self, map):
        self._map = map
        self._cell_height = self._screen_size / self._map.rows
        self._cell_width = self._screen_size / self._map.cols

    def set_game_state(self, game_state):
        self._game_state = game_state
    
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
            (center_x, center_y) = cell.coord.cartesian()

            center_x *= self._cell_width * 0.9
            center_x += self._cell_width * 0.5
            center_y *= self._cell_height * 0.9
            center_y += self._cell_height

            # Get the boundary of the cell.
            boundary = cell.boundary

            # Draw the cell.
            draw_hexagon(self._screen, center_x, center_y, self._cell_width,
                         self._cell_height, color, tile.rotation_degrees,
                         boundary)

    def visualize_actor(self, actor_index):
        actor = self._game_state.actors[actor_index]
        (x, y) = actor.location.cartesian()
        x *= self._cell_width * 0.9
        x += self._cell_width * 0.5
        y *= self._cell_height * 0.9
        y += self._cell_height
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
    """ Reads a JSON MapUpdate from a file provided on the command line and displays it to the user. """
    # Check that the correct number of arguments were provided.
    if len(sys.argv) != 2:
        print("Usage: python visualize.py <map_file>")
        quit()

    # Read file contents and parse them into a JSON MapUpdate.
    with open(sys.argv[1], "r") as file:
        map_update = MapUpdate.from_json(file.read())
        draw_map_and_wait(map_update)

if __name__ == "__main__":
    main()