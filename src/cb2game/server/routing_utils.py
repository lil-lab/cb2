"""A set of utilities for pathfinding and routing in CB2 maps."""
import logging
from collections import deque

from cb2game.server.hex import HecsCoord

logger = logging.getLogger(__name__)


def find_path_to_card(location: HecsCoord, follower, map, cards):
    start_location = follower.location()
    end_location = location
    location_queue = deque()
    location_queue.append((start_location, [start_location]))
    card_locations = set([card.prop_info.location for card in cards])
    if start_location in card_locations:
        card_locations.remove(start_location)
    if end_location in card_locations:
        card_locations.remove(end_location)
    visited_locations = set()
    while len(location_queue) > 0:
        current_location, current_path = location_queue.popleft()
        if current_location in visited_locations:
            continue
        if current_location in card_locations:
            continue
        visited_locations.add(current_location)
        if current_location == end_location:
            return current_path
        tile = map.tile_at(current_location)
        for neighbor in tile.cell.coord.neighbors():
            if tile.cell.boundary.get_edge_between(tile.cell.coord, neighbor):
                continue
            neighbor_tile = map.tile_at(neighbor)
            # This can happen if routing on a follower view with limited map visibility.
            if neighbor_tile is None:
                continue
            if neighbor_tile.cell.boundary.get_edge_between(neighbor, tile.cell.coord):
                continue
            location_queue.append((neighbor, current_path + [neighbor]))
    return None


def get_instruction_to_location(
    location: HecsCoord,
    follower,
    map,
    cards,
    game_endpoint=None,
    default_instruction="random, random, random, random, random, random",
):
    distance_to_follower = lambda c: c.prop_info.location.distance_to(
        follower.location()
    )
    path = find_path_to_card(location, follower, map, cards)
    if not path:
        return default_instruction
    game_vis = game_endpoint.visualization() if game_endpoint else None
    if game_vis is not None:
        game_vis.set_trajectory([(coord, 0) for coord in path])
    heading = follower.heading_degrees() - 60
    instructions = []
    for idx, location in enumerate(path):
        next_location = path[idx + 1] if idx + 1 < len(path) else None
        if not next_location:
            break
        degrees_away = location.degrees_to(next_location) - heading
        if degrees_away < 0:
            degrees_away += 360
        if degrees_away > 180:
            degrees_away -= 360
        # Pre-defined shortcuts to introduce backstepping.
        if degrees_away == 180:
            instructions.append("backward")
            location = next_location
            continue
        if degrees_away == 120:
            instructions.append("left")
            instructions.append("backward")
            heading -= 60
            location = next_location
            continue
        if degrees_away == -120:
            instructions.append("right")
            instructions.append("backward")
            heading += 60
            location = next_location
            continue
        # General-case movement pattern.
        if degrees_away > 0:
            instructions.extend(["right"] * int(degrees_away / 60))
        else:
            instructions.extend(["left"] * int(-degrees_away / 60))
        heading += degrees_away
        instructions.append("forward")
        location = next_location

    return ", ".join(instructions)
