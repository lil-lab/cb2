from server.assets import AssetId
from server.messages.map_update import MapUpdate
from server.messages.bug_report import BugReport
from server.messages.prop import PropType, GenericPropInfo, CardConfig, Prop
from server.card import Shape, Color
from server.hex import HexBoundary, Edges
from server.messages.rooms import Role
from server.actor import Actor

import math
import logging
import pygame
import pygame.font
import random
import sys
import pathlib

import pygame.freetype
pygame.freetype.init()
INSTRUCTION_FONT = pygame.freetype.SysFont('Times New Roman', 30)

logger = logging.getLogger(__name__)

SCREEN_SIZE = 800
SCALE = 5
BORDER = 0

# The width of the follower vision cone in degrees (horizontal). Don't change this without opening Unity and changing the actual follower's FOV (unless you suspect this value isn't accurate).
FOLLOWER_FOV = 96.5

# For various reasons, Unity coordinates are scaled from hex cartesian
# coordinates. This is mostly to line up with a bunch of convenient defaults in
# Unity (camera clipping planes, model sizes, render detail settings, etc). This
# value MUST equal the scale value in game/Assets/Scripts/HexGrid.cs. Don't
# change this without changing that (make sure it's also done in Unity's UI on
# the object component, not just in source code. The default in the editor might
# overwrite that value due to the way Unity works).
UNITY_COORDINATES_SCALE = 3.46

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
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_HOUSE_RED:
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_HOUSE_BLUE:
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_HOUSE_TRIPLE:
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_HOUSE_TRIPLE_RED:
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_HOUSE_TRIPLE_BLUE:
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_HOUSE_GREEN:
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_HOUSE_PINK:
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_HOUSE_ORANGE:
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_HOUSE_YELLOW:
        return pygame.Color("green")
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
    elif asset_id == AssetId.SNOWY_GROUND_TILE:
        return pygame.Color("white")
    elif asset_id == AssetId.SNOWY_MOUNTAIN_TILE:
        return pygame.Color("white")
    elif asset_id == AssetId.SNOWY_RAMP_TO_MOUNTAIN:
        return pygame.Color("white")
    elif asset_id == AssetId.SNOWY_MOUNTAIN_TILE_TREE:
        return pygame.Color("white")
    elif asset_id == AssetId.GROUND_TILE_TREE_SNOW:
        return pygame.Color("green")
    elif asset_id == AssetId.GROUND_TILE_STONES_GREENBUSH:
        return pygame.Color("grey")
    elif asset_id == AssetId.GROUND_TILE_STONES_BROWNBUSH:
        return pygame.Color("grey")
    elif asset_id == AssetId.GROUND_TILE_STONES_GREYBUSH:
        return pygame.Color("grey")
    elif asset_id in [AssetId.GROUND_TILE_TREE, AssetId.GROUND_TILE_TREE_BROWN,
                      AssetId.GROUND_TILE_TREE, AssetId.SNOWY_GROUND_TILE_TREES_2,
                      AssetId.GROUND_TILE_TREE_SOLIDBROWN, AssetId.MOUNTAIN_TILE_TREE,
                      AssetId.GROUND_TILE_TREE_DARKGREEN]:
        return pygame.Color("green")
    else:
        print("Unknown asset ID encountered (color): " + str(asset_id))
        return pygame.Color("white")

def asset_id_to_icon(asset_id):
    if asset_id == AssetId.GROUND_TILE:
        return ""
    elif asset_id == AssetId.GROUND_TILE_ROCKY:
        return "server/map_tools/asset_icons/rocks.png"
    elif asset_id == AssetId.GROUND_TILE_TREES:
        return "server/map_tools/asset_icons/trees.png"
    elif asset_id == AssetId.GROUND_TILE_TREES_2:
        return "server/map_tools/asset_icons/trees.png"
    elif asset_id == AssetId.GROUND_TILE_FOREST:
        return "server/map_tools/asset_icons/trees.png"
    elif asset_id == AssetId.GROUND_TILE_HOUSE:
        return "server/map_tools/asset_icons/house.png"
    elif asset_id == AssetId.GROUND_TILE_HOUSE_RED:
        return "server/map_tools/asset_icons/red_house.png"
    elif asset_id == AssetId.GROUND_TILE_HOUSE_PINK:
        return "server/map_tools/asset_icons/pink_house.png"
    elif asset_id == AssetId.GROUND_TILE_HOUSE_GREEN:
        return "server/map_tools/asset_icons/green_house.png"
    elif asset_id == AssetId.GROUND_TILE_HOUSE_ORANGE:
        return "server/map_tools/asset_icons/orange_house.png"
    elif asset_id == AssetId.GROUND_TILE_HOUSE_YELLOW:
        return "server/map_tools/asset_icons/yellow_house.png"
    elif asset_id == AssetId.GROUND_TILE_HOUSE_BLUE:
        return "server/map_tools/asset_icons/blue_house.png"
    elif asset_id == AssetId.GROUND_TILE_HOUSE_TRIPLE:
        return "server/map_tools/asset_icons/triple_house.png"
    elif asset_id == AssetId.GROUND_TILE_HOUSE_TRIPLE_RED:
        return "server/map_tools/asset_icons/red_triple_house.png"
    elif asset_id == AssetId.GROUND_TILE_HOUSE_TRIPLE_BLUE:
        return "server/map_tools/asset_icons/blue_triple_house.png"
    elif asset_id == AssetId.GROUND_TILE_STREETLIGHT:
        return "server/map_tools/asset_icons/streetlight.png"
    elif asset_id == AssetId.MOUNTAIN_TILE:
        return ""
    elif asset_id == AssetId.RAMP_TO_MOUNTAIN:
        return ""
    elif asset_id == AssetId.GROUND_TILE_PATH:
        return ""
    elif asset_id == AssetId.EMPTY_TILE:
        return ""
    elif asset_id == AssetId.WATER_TILE:
        return ""
    elif asset_id == AssetId.SNOWY_MOUNTAIN_TILE:
        return ""
    elif asset_id == AssetId.SNOWY_MOUNTAIN_TILE_TREE:
        return "server/map_tools/asset_icons/snow_mountain_tree.png"
    elif asset_id == AssetId.SNOWY_RAMP_TO_MOUNTAIN:
        return ""
    elif asset_id == AssetId.MOUNTAIN_TILE_TREE:
        return "server/map_tools/asset_icons/tree.png"
    elif asset_id == AssetId.GROUND_TILE_TREE:
        return "server/map_tools/asset_icons/tree.png"
    elif asset_id == AssetId.GROUND_TILE_TREE_BROWN:
        return "server/map_tools/asset_icons/withered_tree.png"
    elif asset_id == AssetId.GROUND_TILE_TREE_SOLIDBROWN:
        return "server/map_tools/asset_icons/brown_tree.png"
    elif asset_id == AssetId.GROUND_TILE_TREE_DARKGREEN:
        return "server/map_tools/asset_icons/dark_green_tree.png"
    elif asset_id == AssetId.GROUND_TILE_TREE_SNOW:
        return "server/map_tools/asset_icons/snow_tree.png"
    elif asset_id == AssetId.GROUND_TILE_TREES_2:
        return "server/map_tools/asset_icons/tree_2.png"
    elif asset_id == AssetId.SNOWY_GROUND_TILE_TREES_2:
        return "server/map_tools/asset_icons/snow_tree_2.png"
    elif asset_id == AssetId.GROUND_TILE_STONES:
        return "server/map_tools/asset_icons/bush_stone.png"
    elif asset_id == AssetId.GROUND_TILE_STONES_GREENBUSH:
        return "server/map_tools/asset_icons/green_bush_stone.png"
    elif asset_id == AssetId.GROUND_TILE_STONES_BROWNBUSH:
        return "server/map_tools/asset_icons/brown_bush_stone.png"
    elif asset_id == AssetId.GROUND_TILE_STONES_GREYBUSH:
        return "server/map_tools/asset_icons/grey_bush_stone.png"
    else:
        print("Unknown asset ID encountered (img): " + str(asset_id))
        return ""

def draw_wrapped(display, instruction_text, max_width=50):
    words = instruction_text.split(" ")
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) > max_width:
            lines.append(current_line)
            current_line = word
        else:
            current_line += " " + word
    lines.append(current_line)
    screen_size = display._screen_size
    for i, line in enumerate(lines):
        (line_text, _) = INSTRUCTION_FONT.render(line, pygame.Color(90, 90, 90))
        display._screen.blit(line_text, (screen_size * 0.5 - line_text.get_width() / 2, screen_size * 0.75 + i * 30))
    
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
        self._props = None
        self._config = None
        self._state_sync = None
        self._trajectory = None # A list of Hecscoords. A follower's pathway to draw.
        self._positive_markers = None
        self._negative_markers = None
        # Initialize pygame.
        pygame.init()
        # Create the screen
        self._screen = pygame.display.set_mode((self._screen_size,
                                                self._screen_size))
        pygame.display.set_caption("Game Visualizer")
    
    # This is the CB2 server config. Includes fog distance, and some other stuff relevant to game display (card covers, etc.)
    def set_config(self, config):
        self._config = config
    
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
        if hasattr(map, 'props') and map.props:
            self._props = map.props
    
    def set_props(self, props):
        self._props = props
    
    def set_trajectory(self, trajectory):
        self._trajectory = trajectory
    
    def set_positive_markers(self, positive_locations):
        self._positive_markers = positive_locations
    
    def set_negative_markers(self, negative_locations):
        self._negative_markers = negative_locations

    def set_state_sync(self, state_sync):
        self._state_sync = state_sync

    def transform_to_screen_coords(self, coords):
        """ Transforms the given map x, y coordinates to screen coordinates.

            coords: An (x, y) tuple of map coordinates.
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

            asset_icon = asset_id_to_icon(asset_id)            
            if not pathlib.Path(asset_icon).is_file():
                continue
            # Draw the asset label.
            icon = pygame.image.load(asset_icon)
            icon.convert()
            icon_width = int(self._cell_width * 0.8)
            icon_height = int(self._cell_height * 0.8)
            icon = pygame.transform.scale(icon, (icon_width, icon_height))
            self._screen.blit(icon, (center_x - icon_width/2, center_y - icon_height/2))

    def visualize_props(self):
        if self._props is None:
            return

        # Draw card props.
        for prop in self._props:
            if prop.prop_type != PropType.CARD:
                continue
            # Get the card location.
            loc = prop.prop_info.location
            (center_x, center_y) = self.transform_to_screen_coords(loc.cartesian())
            draw_card(self._screen, center_x, center_y,
                      self._cell_width / 2, self._cell_height * 0.7,
                      prop.card_init)

    def visualize_actor(self, actor_index):
        actor = self._state_sync.actors[actor_index]
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
    
    def set_instructions(self, instructions):
        self._instructions = instructions
    
    def visualize_state_sync(self):
        if self._map is None or self._state_sync is None:
            return
        for i in range(self._state_sync.population):
            self.visualize_actor(i)
    
    def visualize_trajectory(self):
        if self._trajectory is None or len(self._trajectory) == 0:
            return
        base_trajectory_color = pygame.Color("lightskyblue")
        offset = (random.uniform(-3, 3), random.uniform(-3, 3))
        for i in range(len(self._trajectory) - 1):
            (pos, heading) = self._trajectory[i]
            (next_pos, next_heading) = self._trajectory[i + 1]
            (x1, y1) = self.transform_to_screen_coords(pos.cartesian())
            (x2, y2) = self.transform_to_screen_coords(next_pos.cartesian())
            if x1 == x2 and y1 == y2:
                continue
            # Offset the trajectory coordinates with a small amount of noise so that lines don't overlap in the center.
            x1 += offset[0]
            y1 += offset[1]
            offset = (random.uniform(-3, 3), random.uniform(-3, 3))
            x2 += offset[0]
            y2 += offset[1]
            # Choose a color that gets brighter with each segment
            trajectory_color = pygame.Color(base_trajectory_color)
            trajectory_color.hsva = (trajectory_color.hsva[0], trajectory_color.hsva[1],
                                    max(trajectory_color.hsva[2] - i * 1, 0),
                                    trajectory_color.hsva[3])
            pygame.draw.line(self._screen, trajectory_color, (x1, y1), (x2, y2), 2)
        # Draw a circle at the beginning of the trajectory.
        (start_pos, start_heading) = self._trajectory[0]
        (x, y) = self.transform_to_screen_coords(start_pos.cartesian())
        pygame.draw.circle(self._screen, base_trajectory_color, (x, y), 10)

        # Draw the initial heading of the actor.
        heading = start_heading - 60
        heading_offset = 6
        x_offset = heading_offset * math.cos(math.radians(heading))
        y_offset = heading_offset * math.sin(math.radians(heading))
        pygame.draw.circle(self._screen, pygame.Color("black"), (x + x_offset, y + y_offset), 4)

    def visualize_markers(self):
        if self._positive_markers is None or len(self._positive_markers) == 0:
            return
        for (hecs, orientation) in self._positive_markers:
            (x, y) = self.transform_to_screen_coords(hecs.cartesian())
            heading = orientation - 60
            orientation_offset = 15
            x_offset = orientation_offset * math.cos(math.radians(heading))
            y_offset = orientation_offset * math.sin(math.radians(heading))
            pygame.draw.circle(self._screen, pygame.Color("green"), (x + x_offset, y + y_offset), 7)

        if self._negative_markers is None or len(self._negative_markers) == 0:
            return
        
        for (hecs, orientation) in self._negative_markers:
            (x, y) = self.transform_to_screen_coords(hecs.cartesian())
            heading = orientation - 60
            orientation_offset = 15
            x_offset = orientation_offset * math.cos(math.radians(heading))
            y_offset = orientation_offset * math.sin(math.radians(heading))
            pygame.draw.circle(self._screen, pygame.Color("red"), (x + x_offset, y + y_offset), 7)
        
    def visualize_follower_visibility(self):
        if self._config is None:
            return
        follower = None
        for i, actor in enumerate(self._state_sync.actors):
            if actor.actor_role == Role.FOLLOWER:
                follower = Actor(i, 0, Role.FOLLOWER, actor.location, False, actor.rotation_degrees)
                break
        if follower is None:
            return
        fog_distance_hex_coordinates = self._config["fog_end"] / UNITY_COORDINATES_SCALE
        pygame_distance = fog_distance_hex_coordinates
        follower_location = follower.location().cartesian()

        box_corner = self.transform_to_screen_coords((follower_location[0] - pygame_distance, follower_location[1] - pygame_distance))
        box_corner_2 = self.transform_to_screen_coords((follower_location[0] + pygame_distance, follower_location[1] + pygame_distance))
        box_width = box_corner_2[0] - box_corner[0]
        box_height = box_corner_2[1] - box_corner[1]
        box_around_follower = pygame.Rect(
            box_corner[0], # Left.
            box_corner[1], # Top.
            box_width,
            box_height)
        follower_left_angle_degrees = (follower.heading_degrees() - 60) - FOLLOWER_FOV / 2
        follower_right_angle_degrees = (follower.heading_degrees() - 60) + FOLLOWER_FOV / 2
        # Convert to radians
        follower_left_angle_radians = math.radians(follower_left_angle_degrees)
        follower_right_angle_radians = math.radians(follower_right_angle_degrees)
        pygame.draw.arc(self._screen, pygame.Color(0, 100, 200, 200), box_around_follower, -follower_right_angle_radians, -follower_left_angle_radians, 3)
        arc_endpoint = (follower_location[0] + pygame_distance * math.cos(follower_left_angle_radians), follower_location[1] + pygame_distance * math.sin(follower_left_angle_radians))
        pygame.draw.line(
            self._screen,
            pygame.Color(0, 100, 200, 200),
            self.transform_to_screen_coords(follower_location),
            self.transform_to_screen_coords(arc_endpoint),
            3) # Width.
        arc_endpoint_2 = (follower_location[0] + pygame_distance * math.cos(follower_right_angle_radians), follower_location[1] + pygame_distance * math.sin(follower_right_angle_radians))
        pygame.draw.line(
            self._screen,
            pygame.Color(0, 100, 200, 200),
            self.transform_to_screen_coords(follower_location),
            self.transform_to_screen_coords(arc_endpoint_2),
            3) # Width.

    def visualize_instructions(self):
        if not self._instructions or len(self._instructions) == 0:
            return
        text = ""
        for instruction in self._instructions:
            if instruction.cancelled or instruction.completed:
                continue
            text += instruction.text + "|"
        draw_wrapped(self, text)

    def draw(self):
        # Fill the screen with white
        self._screen.fill((255,255,255))
        # Draw map elements.
        self.visualize_map()
        self.visualize_props()
        self.visualize_state_sync()
        self.visualize_trajectory()
        self.visualize_markers()
        self.visualize_follower_visibility()
        self.visualize_instructions()

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
