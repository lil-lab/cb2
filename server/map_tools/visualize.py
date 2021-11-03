from assets import AssetId
from messages.map_update import MapUpdate
from hex import HexBoundary, Edges

import math
import pygame
import sys

SCREEN_SIZE = 1000
SCALE = 20

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
    
        Returns the color.
    """
    return pygame.Color("black")

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
        angle = i * 60 - 30 + rotation

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
    pygame.draw.polygon(screen, color, vertices, 1)

    line_width = 10
    if boundary.get_edge(Edges.UPPER_RIGHT):
        pygame.draw.line(screen, pygame.Color("red"), vertices[0], vertices[1], line_width)
    
    if boundary.get_edge(Edges.RIGHT):
        pygame.draw.line(screen, pygame.Color("red"), vertices[1], vertices[2], line_width)
        
    if boundary.get_edge(Edges.LOWER_RIGHT):
        pygame.draw.line(screen, pygame.Color("red"), vertices[2], vertices[3], line_width)

    if boundary.get_edge(Edges.LOWER_LEFT):
        pygame.draw.line(screen, pygame.Color("red"), vertices[3], vertices[4], line_width)
    
    if boundary.get_edge(Edges.LEFT):
        pygame.draw.line(screen, pygame.Color("red"), vertices[4], vertices[5], line_width)
    
    if boundary.get_edge(Edges.UPPER_LEFT):
        pygame.draw.line(screen, pygame.Color("red"), vertices[5], vertices[0], line_width)

def visualize_map(map_update):
    """ Takes a message of type MapUpdate and draws each hex cell to the screen using pygame."""
        # Initialize pygame
    pygame.init()

    # Create the screen
    screen = pygame.display.set_mode((SCREEN_SIZE, SCREEN_SIZE))
    pygame.display.set_caption("Map")

    # Fill the screen with white
    screen.fill((255,255,255))

    cell_height = SCREEN_SIZE / map_update.rows
    cell_width = SCREEN_SIZE / map_update.cols

    # Create a text surface to render text onto.
    myfont = pygame.font.SysFont('Comic Sans MS', 30)

    # Draw the map
    for tile in map_update.tiles:
        # Get the tile color.
        asset_id = tile.asset_id
        color = asset_id_to_color(asset_id)

        # Get the center of the hexagonal cell.
        cell = tile.cell
        (center_x, center_y) = cell.coord.cartesian()

        center_x *= cell_width * 0.9
        center_x += cell_width * 0.5
        center_y *= cell_height * 0.9
        center_y += cell_height

        # Get the boundary of the cell.
        boundary = HexBoundary.rotate_cw(cell.boundary, tile.rotation_degrees // 60)

        asset_text = myfont.render("a: " + asset_id_to_text(asset_id), False, (0, 0, 0))
        bound_text = myfont.render("b: " + str(boundary.edges), False, (0, 0, 0))
        screen.blit(asset_text, (center_x - 30, center_y - 15))
        screen.blit(bound_text, (center_x - 30, center_y + 15))

        # Draw the cell.
        draw_hexagon(screen, center_x, center_y, cell_width, cell_height, color, tile.rotation_degrees, boundary)

    # Update the screen
    pygame.display.flip()

    # Wait for a key to be pressed
    wait_for_key()

def main():
    """ Reads a JSON MapUpdate from a file provided on the command line and displays it to the user. """
    # Check that the correct number of arguments were provided.
    if len(sys.argv) != 2:
        print("Usage: python visualize.py <map_file>")
        quit()

    # Read file contents and parse them into a JSON MapUpdate.
    with open(sys.argv[1], "r") as file:
        map_update = MapUpdate.from_json(file.read())
        visualize_map(map_update)

if __name__ == "__main__":
    main()