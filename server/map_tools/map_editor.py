import dataclasses
import logging
import math
import random
import tkinter
from tkinter.filedialog import askopenfilename, asksaveasfilename
from typing import Tuple

import pygame
import pygame.font
import pygame.freetype

import server.hex as hex
from server.assets import AssetId
from server.card import Card
from server.card_enums import Color, Shape
from server.map_tools.visualize import (
    GameDisplay,
    PygameColorFromCardColor,
    asset_id_to_color,
    draw_card,
    draw_shape,
    draw_tile,
)
from server.map_utils import (
    GroundTile,
    GroundTileForest,
    GroundTileHouse,
    GroundTileRocky,
    GroundTileRockySnow,
    GroundTileSnow,
    GroundTileStones,
    GroundTileStonesSnow,
    GroundTileStreetLight,
    GroundTileStreetLightFoilage,
    GroundTileTree,
    GroundTileTreeBrown,
    GroundTileTreeRocks,
    GroundTileTreeRocksSnow,
    GroundTileTrees,
    GroundTileTreeSnow,
    HecsCoord,
    HouseType,
    MountainTile,
    MountainTileTree,
    PathTile,
    RampToMountain,
    WaterTile,
    copy,
)
from server.messages.scenario import Scenario
from server.util import IdAssigner, JsonSerialize

pygame.freetype.init()
FONT = pygame.freetype.SysFont("Arial", 30)

logger = logging.getLogger(__name__)

# The size of the map. We override the pygame window size to add tool panels.
SCREEN_SIZE = 800

tile_generators = [
    GroundTile,
    GroundTileSnow,
    WaterTile,
    PathTile,
    GroundTileRocky,
    GroundTileRockySnow,
    GroundTileStones,
    GroundTileStonesSnow,
    GroundTileTrees,
    GroundTileTree,
    GroundTileTreeBrown,
    GroundTileTreeSnow,
    GroundTileTreeRocks,
    GroundTileTreeRocksSnow,
    GroundTileForest,
    lambda x: GroundTileHouse(x, HouseType.HOUSE),
    lambda x: GroundTileHouse(x, HouseType.HOUSE_RED),
    lambda x: GroundTileHouse(x, HouseType.HOUSE_BLUE),
    lambda x: GroundTileHouse(x, HouseType.HOUSE_PINK),
    lambda x: GroundTileHouse(x, HouseType.HOUSE_GREEN),
    lambda x: GroundTileHouse(x, HouseType.HOUSE_YELLOW),
    lambda x: GroundTileHouse(x, HouseType.HOUSE_ORANGE),
    lambda x: GroundTileHouse(x, HouseType.TRIPLE_HOUSE),
    lambda x: GroundTileHouse(x, HouseType.TRIPLE_HOUSE_RED),
    lambda x: GroundTileHouse(x, HouseType.TRIPLE_HOUSE_BLUE),
    GroundTileStreetLight,
    GroundTileStreetLightFoilage,
    MountainTile,
    MountainTileTree,
    RampToMountain,
    lambda x: MountainTile(x, True),  # Snowy
    lambda x: MountainTileTree(x, True),  # Snowy
    lambda x: RampToMountain(x, True),  # Snowy
]


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


def distance(x: Tuple[float, float], y: Tuple[float, float]):
    return math.sqrt((x[0] - y[0]) ** 2 + (x[1] - y[1]) ** 2)


def add_map_boundaries(rows, cols, tiles):
    """Adds boundaries to the hex map edges."""
    for i, t in enumerate(tiles):
        loc = t.cell.coord
        for n in loc.neighbors():
            (nr, nc) = n.to_offset_coordinates()
            # If the neighbor cell is outside the map, add an edge to this cell's boundary.
            if not (0 < nr < rows and 0 < nc < cols):
                tiles[i].cell.boundary.set_edge_between(loc, n)


def edit_scenario(scenario: Scenario) -> Scenario:
    # Draws the map and also allows the user to edit it. Draw a tool window on the right with all asset types and a tool panel on the bottom with card options.
    display = GameDisplay(SCREEN_SIZE)
    display.init_pygame(screen_size_override=SCREEN_SIZE + 200)
    pygame.display.set_caption("Map Editor")

    # Prune the map of all tiles with coordinates that are outside the map size.
    pruned_tiles = []
    for tile in scenario.map.tiles:
        (r, c) = tile.cell.coord.to_offset_coordinates()
        if 0 < r < scenario.map.rows and 0 < c < scenario.map.cols:
            pruned_tiles.append(tile)
    scenario.map.tiles = pruned_tiles

    # Add layer boundaries.
    add_map_boundaries(scenario.map.rows, scenario.map.cols, scenario.map.tiles)

    # Prune the map of all props with coordinates that are outside the map size.
    pruned_props = []
    for prop in scenario.prop_update.props:
        (r, c) = prop.prop_info.location.to_offset_coordinates()
        if 0 < r < scenario.map.rows and 0 < c < scenario.map.cols:
            pruned_props.append(prop)
    pruned_prop_update = dataclasses.replace(scenario.prop_update, props=pruned_props)
    scenario = dataclasses.replace(scenario, prop_update=pruned_prop_update)

    # Now move all actors outside the map to the center of the map.
    pruned_actors = []
    for actor in scenario.actor_state.actors:
        (r, c) = actor.location.to_offset_coordinates()
        if 0 < r < scenario.map.rows and 0 < c < scenario.map.cols:
            pruned_actors.append(actor)
        else:
            # Choose a random location in the map.
            (r, c) = (
                random.randint(0, scenario.map.rows),
                random.randint(0, scenario.map.cols),
            )
            logger.info(
                f"Moving actor {actor.actor_id} to random location {(r,c)} in map."
            )
            pruned_actors.append(
                dataclasses.replace(actor, location=HecsCoord.from_offset(r, c))
            )
    pruned_actor_state = dataclasses.replace(scenario.actor_state, actors=pruned_actors)
    scenario = dataclasses.replace(scenario, actor_state=pruned_actor_state)

    # We now have a map in the region (0, 0, SCREEN_SIZE, SCREEN_SIZE). We want
    # to draw a tool window on the right and a tool panel on the bottom. And an
    # exit button in the top right.

    # Draw the tool window.
    tool_window_height = (len(tile_generators) // 3 + 1) * 50 + 10
    tool_window = pygame.Surface((170, tool_window_height))
    tool_window.fill((200, 230, 230))

    # Each panel in the tool window is an icon from the asset list. Draw it in a Nx2 grid vertically.
    tile_generator_coords = {}
    for i, tile_generator in enumerate(tile_generators):
        coordinates = ((i % 3) * 50 + 35, (i // 3) * 50 + 35)
        global_coordinates = (coordinates[0] + SCREEN_SIZE, coordinates[1] + 10)
        tile = tile_generator(0)  # Rotation 0.
        draw_tile(tool_window, tile, coordinates, 50, 50)
        tile_generator_coords[global_coordinates] = tile_generator

    # Now create a panel for editing cards along the bottom of the window. For cards, have 3 rows.
    # The first row is the card symbol. The second row is the card color. The third row the card number.
    # The first row should allow the user to select from a member of the Shape enum.
    # The second row should allow the user to select from a member of the Color enum.
    # The third row should allow the user to select from integers 1-3 (inclusive).

    # Draw the card tool panel.
    card_panel = pygame.Surface((SCREEN_SIZE - 250, 150))
    card_panel.fill((200, 230, 230))

    # Draw card options in the panel.
    card_shape_coords = {}
    for shape in Shape:
        if shape == Shape.NONE:
            continue
        if shape == Shape.MAX:
            continue
        coordinates = (shape.value * 50 + 15, 35)
        global_coordinates = (coordinates[0] + 50, coordinates[1] + SCREEN_SIZE - 200)
        # Draw the shape. Scale it up by 2x.
        logger.info(f"Drawing shape {shape} at {coordinates}")
        draw_shape(
            card_panel,
            coordinates[0],
            coordinates[1],
            shape,
            PygameColorFromCardColor(Color.BLUE),
        )
        card_shape_coords[global_coordinates] = shape
    card_color_coords = {}
    for color in Color:
        if color == Color.NONE:
            continue
        if color == Color.MAX:
            continue
        coordinates = (color.value * 50 + 15, 85)
        global_coordinates = (coordinates[0] + 50, coordinates[1] + SCREEN_SIZE - 200)
        pygame_color = PygameColorFromCardColor(color)
        logger.info(f"Drawing color {color} at {coordinates} with color {pygame_color}")
        draw_shape(
            card_panel, coordinates[0], coordinates[1], Shape.SQUARE, pygame_color
        )
        card_color_coords[global_coordinates] = color
    card_number_coords = {}
    for i in range(0, 4):
        coordinates = (i * 50 + 60, 115)
        global_coordinates = (coordinates[0] + 60, coordinates[1] + SCREEN_SIZE - 190)
        # Write the number on the card.
        (text, _) = FONT.render(str(i), pygame.Color(90, 90, 90))
        card_panel.blit(text, coordinates)
        card_number_coords[global_coordinates] = i

    # Draw the save button.
    save_button = pygame.Surface((50, 50))
    save_button.fill((0, 255, 0))
    save_button_rect = pygame.rect.Rect(
        SCREEN_SIZE + 0, tool_window_height + 50, 50, 50
    )
    # Draw the text save on the button.
    text, _ = FONT.render("Save", True, (0, 0, 0))
    save_button.blit(text, save_button_rect.center)

    # Draw a clear all button.
    clear_button = pygame.Surface((50, 50))
    clear_button.fill((255, 0, 0))
    clear_button_rect = pygame.rect.Rect(
        SCREEN_SIZE + 50, tool_window_height + 50, 50, 50
    )
    # Draw the text clear on the button.
    text, _ = FONT.render("Clear", True, (0, 0, 0))
    clear_button.blit(text, clear_button_rect.center)

    id_assigner = IdAssigner()
    # Make sure we don't reassign IDs which are already in use.
    for prop in scenario.prop_update.props:
        id_assigner.alloc()

    # Prerender selected tool indicator.
    selected_tool_surface = pygame.Surface((50, 50))
    selected_tool_surface.fill(pygame.Color(255, 255, 255, 0))
    selected_tool_surface.set_alpha(128)
    pygame.draw.rect(
        selected_tool_surface, (0, 100, 255), (0, 0, 50, 50), 3
    )  # width = 3

    active_color = Color.RED
    active_shape = Shape.SQUARE
    active_number = 1
    active_card = None
    active_tool_surface = None
    active_tool = None
    tool_location = None
    current_rotation = 0
    # Interactive UI.
    while True:
        display.set_map(scenario.map)
        display.set_props(scenario.prop_update.props)
        display.set_state_sync(scenario.actor_state)

        display.draw()
        # Draw a version of the tool around the mouse.
        if active_tool_surface is not None:
            # Draw the active tool on the screen.
            mouse_pos = pygame.mouse.get_pos()
            display._screen.blit(
                active_tool_surface, (mouse_pos[0] - 25, mouse_pos[1] - 25)
            )  # pylint: disable=protected-access

        # Display which tool is selected.
        if active_tool is not None:
            # Draw selected_tool_surface around the active tool.
            tool_location = None
            for location, tool in tile_generator_coords.items():
                if tool == active_tool:
                    tool_location = location
                    break

        # Draw the tool panels.
        display._screen.blit(
            tool_window, (SCREEN_SIZE, 10)
        )  # pylint: disable=protected-access
        display._screen.blit(
            card_panel, (50, SCREEN_SIZE - 200)
        )  # pylint: disable=protected-access
        display._screen.blit(save_button, save_button_rect)
        display._screen.blit(clear_button, clear_button_rect)

        # Display which card parameters are selected, and draw the card around the mouse.
        if active_card is not None:
            # Draw the selected_tool_surface around the active color, shape, and number menu options.
            # Draw the selected_tool_surface around the active color.
            color_location = None
            for location, color in card_color_coords.items():
                if color is active_color:
                    color_location = location
                    break
            if color_location is not None:
                display._screen.blit(
                    selected_tool_surface,
                    (color_location[0] - 25, color_location[1] - 25),
                )  # pylint: disable=protected-access
            # Draw the selected_tool_surface around the active shape.
            shape_location = None
            for location, shape in card_shape_coords.items():
                if shape is active_shape:
                    shape_location = location
                    break
            if shape_location is not None:
                display._screen.blit(
                    selected_tool_surface,
                    (shape_location[0] - 25, shape_location[1] - 25),
                )  # pylint: disable=protected-access
            # Draw the selected_tool_surface around the active number.
            number_location = None
            for location, number in card_number_coords.items():
                if number is active_number:
                    number_location = location
                    break
            if number_location is not None:
                display._screen.blit(
                    selected_tool_surface,
                    (number_location[0] - 25, number_location[1] - 25),
                )  # pylint: disable=protected-access

        # Find the map tile closest to the mouse.
        mouse_pos = pygame.mouse.get_pos()
        for coordinate, tile in display.tile_coordinates_map().items():
            if distance(coordinate, mouse_pos) < 15:
                active_tool_color = (
                    asset_id_to_color(active_tool(0).asset_id)
                    if active_tool is not None
                    else pygame.Color("purple")
                )
                display.set_selected_tile(tile, active_tool_color)
                break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return scenario
            # If Q or ESC is pressed, quit.
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                    return scenario
            # On click, set the active tool.
            if event.type == pygame.MOUSEBUTTONDOWN:
                if save_button_rect.collidepoint(event.pos):
                    return scenario
                if clear_button_rect.collidepoint(event.pos):
                    logger.info(f"Clearing tile {i}")
                    for i, tile in enumerate(scenario.map.tiles):
                        tile.cell.boundary = hex.HexBoundary(0)
                        tile.cell.layer = 0
                        tile.cell.height = LayerToHeight(tile.cell.layer)
                        scenario.map.tiles[i] = dataclasses.replace(
                            tile,
                            asset_id=AssetId.GROUND_TILE,
                        )
                    continue

                # Check for tile tooltip clicks.
                found_tool = False
                for coordinates, tile_generator in tile_generator_coords.items():
                    if distance(coordinates, event.pos) < 25:
                        # Clicking on the same tool rotates it 60 deg.
                        if active_tool is tile_generator:
                            current_rotation += 60
                        else:
                            current_rotation = 0
                        active_card = None
                        active_tool = tile_generator
                        active_tool_surface = pygame.Surface((50, 50))
                        # Make the surface transparent.
                        active_tool_surface.set_colorkey((0, 0, 0))
                        # Make transparency 50%.
                        active_tool_surface.set_alpha(128)
                        draw_tile(
                            active_tool_surface,
                            active_tool(current_rotation),
                            (25, 25),
                            50,
                            50,
                        )
                        found_tool = True
                        break

                # Check for card tooltip clicks.
                found_card = False
                for coordinates, shape in card_shape_coords.items():
                    if distance(coordinates, event.pos) < 15:
                        active_shape = shape
                        found_card = True
                        break
                for coordinates, color in card_color_coords.items():
                    if distance(coordinates, event.pos) < 15:
                        active_color = color
                        found_card = True
                        break
                for coordinates, number in card_number_coords.items():
                    if distance(coordinates, event.pos) < 15:
                        active_number = number
                        found_card = True
                        break
                if found_card:
                    tool_location = None
                    active_card = Card(
                        id_assigner.alloc(),
                        HecsCoord.origin,
                        0,
                        active_shape,
                        active_color,
                        active_number,
                        False,
                    )
                    active_tool_surface = pygame.Surface((50, 50))
                    # Make the surface transparent.
                    active_tool_surface.set_colorkey((0, 0, 0))
                    # Make transparency 50%.
                    active_tool_surface.set_alpha(128)
                    draw_card(active_tool_surface, 25, 25, 50, 50, active_card)
                    found_tool = True

                # Check for map clicks.
                found_map_tile = False
                for coordinate, tile in display.tile_coordinates_map().items():
                    if distance(coordinate, event.pos) < 20:
                        # We clicked on a map tile. Set the tile to the active tool.
                        if active_tool is not None:
                            for i, map_tile in enumerate(scenario.map.tiles):
                                if map_tile.cell.coord == tile.cell.coord:
                                    # Remove the old tile.
                                    scenario.map.tiles.pop(i)
                                    break
                            gen_tile = active_tool(current_rotation)
                            # Set the coordinate.
                            gen_tile.cell.coord = tile.cell.coord
                            scenario.map.tiles.append(gen_tile)
                        if active_card is not None:
                            for i, prop in enumerate(scenario.prop_update.props):
                                if prop.prop_info.location == tile.cell.coord:
                                    # Remove the old prop.
                                    scenario.prop_update.props.pop(i)
                                    break
                            if active_number > 0:
                                # Set the coordinate.
                                new_card = copy.deepcopy(active_card)
                                new_card.location = tile.cell.coord
                                scenario.prop_update.props.append(new_card.prop())
                        found_map_tile = True
                        break
                if not found_tool and not found_map_tile and not found_card:
                    active_tool = None
                    active_card = None
                    active_tool_surface = None
                    tool_location = None
                    current_rotation = 0
        # Display currently selected tool.
        if tool_location is not None:
            display._screen.blit(
                selected_tool_surface, (tool_location[0] - 25, tool_location[1] - 25)
            )
        # Draw the cursor.
        mouse_pos = pygame.mouse.get_pos()
        pygame.draw.circle(
            display._screen, (255, 0, 0), mouse_pos, 5, 1
        )  # pylint: disable=protected-access
        pygame.display.flip()


def main():
    """Reads a JSON scenario from a file provided on the command line and gives an interactive display to the user, allowing them to edit the map."""
    logging.basicConfig(level=logging.INFO)

    root = tkinter.Tk()
    root.overrideredirect(1)
    root.withdraw()

    pygame.init()

    scenario_file = askopenfilename()
    # Read file contents and parse them into a JSON MapUpdate.
    with open(scenario_file, "r") as file:
        scenario = Scenario.from_json(file.read())
        edited_scenario = edit_scenario(scenario)

    # Write the edited map to a file.
    filename = asksaveasfilename(
        confirmoverwrite=True, title="Save Scenario", defaultextension=".json"
    )
    if filename == "":
        return

    logger.info(f"Writing to {filename}")
    with open(filename, "w") as file:
        file.write(JsonSerialize(edited_scenario))


if __name__ == "__main__":
    main()
