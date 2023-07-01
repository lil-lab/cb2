from typing import List

from cb2game.pyclient.follower_data_masking import CoordinateIsVisible
from cb2game.server.actor import Actor
from cb2game.server.assets import AssetId
from cb2game.server.config.config import Config
from cb2game.server.hex import HecsCoord
from cb2game.server.map_utils import AssetId, NatureAssetIds, TreeAssetIds
from cb2game.server.messages.map_update import MapUpdate
from cb2game.server.messages.objective import ObjectiveMessage
from cb2game.server.messages.prop import PropType, PropUpdate
from cb2game.server.messages.turn_state import TurnState
from cb2game.server.routing_utils import get_instruction_to_location


def DescribeBearingFromActor(location: HecsCoord, actor: Actor) -> str:
    """Returns a string describing the given location from the perspective of the given actor."""
    distance = round(actor.location().distance_to(location), 1)
    direction = (
        -(
            round(
                actor.heading_degrees()
                - actor.location().degrees_to_precise(location)
                - 60,
                1,
            )
        )
        % 360
    )
    # If we're standing on the tile, give a heading of zero.
    if distance == 0:
        direction = 0
    return f"distance: {distance} units and heading: {direction} degrees"


def DescribeLocationFromActor(location: HecsCoord, actor: Actor, map, cards) -> str:
    """Returns a string describing the given location from the perspective of the given actor."""
    if actor.location() == location:
        return "You are standing here."
    default_instruction = "<Cannot reach>"
    instruction = get_instruction_to_location(
        location, actor, map, cards, default_instruction=default_instruction
    )
    if instruction == default_instruction:
        return f"Path not in sight. {DescribeBearingFromActor(location, actor)}"
    return f"Path to reach: {instruction}"


def FollowerSystemPrompt() -> str:
    system_prompt = (
        "GAME EXPLANATION: \n"
        "You are playing a text-based videogame. In this game, you are the FOLLOWER. "
        "Your role is to follow the ACTIVE instruction. "
        "First you must type in your thoughts. You can do this by starting a line with 'THOUGHTS:' and then typing your thoughts on the same line (important!). "
        "Then type in your intended action. You can do this by starting a line with 'ACTIONS:' and then typing a comma-separate list of actions, ending with newline."
        "E.G. a List of: 'R', 'L', 'F', 'B', or 'D' (Right, Left, Forward, Back, Done). Actions MUST be one of these single-letters. "
        "Use 'D' to mark the instruction as completed. "
        "You cannot see things behind you or to the sides. You also can't see things that are too far away. Turn around or move to explore. "
        "After a few observations, if you're lost, use a 'D'one action to get a new instruction. "
        "Headings are described in degrees, with positive meaning to the right and "
        "negative meaning to the left. You are on a discrete hex grid, each turn is 60 degrees. "
        "You get a new observation each time you move. Do not hit 'done' until "
        "you have completed the instruction. The leader can see things you can't, "
        "so trust instructions. After each ACTION line, you will get a new observation, so you can explore a bit. "
        "There are no traps, so explore freely. Outposts, and cities are just waypoints, and have no clues."
    )
    return system_prompt


def SingleActionSystemPrompt() -> str:
    system_prompt = (
        "GAME EXPLANATION: \n"
        "You are playing a text-based videogame. In this game, you are the FOLLOWER. "
        "Your role is to follow the ACTIVE instruction. "
        "First type in your thoughts. You can do this by starting a line with 'THOUGHTS:' and then typing your thoughts. "
        "Then type in your intended action. You can do this by starting a line with 'ACTION:' and then typing only a single action, ending with newline."
        "E.G. one of: 'R', 'L', 'F', and 'B' (Right, Left, Forward, and Back). "
        "You can also write 'D', to mark an instruction as completed. "
        "You cannot see things behind you or to the sides. You also can't see things that are too far away. Turn around or move to explore. "
        "After a few observations, if you're lost, use a 'D' action to get a new instruction. "
        "Headings are described in degrees, with positive meaning to the right and "
        "negative meaning to the left. You are on a discrete hex grid, each turn is 60 degrees. "
        "You get a new observation each time you move. Do not hit 'done' until "
        "you have completed the instruction. The leader can see things you can't, "
        "so trust instructions. After each ACTION line, you will get a new observation, so you can explore a bit. "
        "There are no traps, so explore freely. Outposts, and cities are just waypoints, and have no clues."
    )
    return system_prompt


def DescribeMap(
    map_update: MapUpdate,
    prop_update: PropUpdate,
    instructions: List[ObjectiveMessage],
    turn_state: TurnState,
    follower: Actor,
    leader: Actor = None,
) -> str:
    """Returns a string describing the given map."""
    header = f"MAP DIMENSIONS:\n\t{map_update.rows}x{map_update.cols} hexagon map with {len(prop_update.props)} props. \n"

    cards = [prop for prop in prop_update.props if prop.prop_type == PropType.CARD]

    fog_end = map_update.fog_end
    if fog_end is None:
        # Create a config object and use the default value.
        default_config = Config()
        fog_end = default_config.fog_end

    instruction_descriptions = []
    for i, instruction in enumerate(instructions):
        # Determine instruction status from instruction.completed, instruction.cancelled (if neither, then in progress).
        if instruction.completed:
            status = "completed"
        elif instruction.cancelled:
            status = "cancelled"
        else:
            status = "ACTIVE"
        instruction_descriptions.append(
            f"Status: {status}, Instruction: {instruction.text}"
        )
        # There can only be one active instruction at a time. Any instructions after this are queued for future reveal. End iteration.
        if status == "ACTIVE":
            break

    # Print each instruction description on a line, indented:
    instruction_section = "INSTRUCTIONS\n"
    for instruction in instruction_descriptions:
        instruction_section += f"\t{instruction}\n"

    # Describe the turn state
    turn_state_description = f"Moves remaining: {turn_state.moves_remaining}.\n\tWho's turn it is: {turn_state.turn}.\n\tTurns left before end of game: {turn_state.turns_left}.\n\tCurrent Score: {turn_state.score}.\n\tGame Over:{turn_state.game_over}\n"

    # Describe the props
    prop_descriptions = []
    for prop in prop_update.props:
        if prop.prop_type == PropType.CARD:
            location_description = DescribeLocationFromActor(
                prop.prop_info.location, follower, map_update, cards
            )
            # Only show shape, color, count for selected cards.
            if prop.card_init.selected:
                prop_descriptions.append(
                    f"Selected card at {location_description}. Shape {prop.card_init.shape.name}, color {prop.card_init.color.name}, count {prop.card_init.count}"
                )
            else:
                prop_descriptions.append(f"Card at {location_description}.")
    # Describe the map metadata
    metadata = map_update.metadata
    metadata_descriptions = []
    for lake in metadata.lakes:
        if CoordinateIsVisible(
            HecsCoord.from_offset(lake.r, lake.c), follower, fog_end
        ):
            location_description = DescribeLocationFromActor(
                HecsCoord.from_offset(lake.r, lake.c), follower, map_update, cards
            )
            metadata_descriptions.append(
                f"Lake of size {lake.size} and shape {lake.type.name} at {location_description}."
            )
    for mountain in metadata.mountains:
        if CoordinateIsVisible(
            HecsCoord.from_offset(mountain.r, mountain.c), follower, fog_end
        ):
            location_description = DescribeLocationFromActor(
                HecsCoord.from_offset(mountain.r, mountain.c),
                follower,
                map_update,
                cards,
            )
            metadata_descriptions.append(
                f"{mountain.type.name} mountain{' (snowy)' if mountain.snowy else ''} at {location_description}."
            )
    for city in metadata.cities:
        if CoordinateIsVisible(
            HecsCoord.from_offset(city.r, city.c), follower, fog_end
        ):
            location_description = DescribeLocationFromActor(
                HecsCoord.from_offset(city.r, city.c), follower, map_update, cards
            )
            metadata_descriptions.append(
                f"City of size {city.size} at {location_description}."
            )
    for outpost in metadata.outposts:
        if CoordinateIsVisible(
            HecsCoord.from_offset(outpost.r, outpost.c), follower, fog_end
        ):
            location_description = DescribeLocationFromActor(
                HecsCoord.from_offset(outpost.r, outpost.c), follower, map_update, cards
            )
            metadata_descriptions.append(f"Outpost at {location_description}.")

    # If provided, and if visible, describe the leader.
    if leader:
        if CoordinateIsVisible(leader.location(), follower, fog_end):
            leader_location = DescribeLocationFromActor(
                leader.location(), follower, map_update, cards
            )
            metadata_descriptions.append(f"Leader at {leader_location}.")

    # Describe nearby tiles
    nearby_tiles = []
    follower_forward = follower.location().neighbor_at_heading(
        follower.heading_degrees()
    )
    follower_left = follower.location().neighbor_at_heading(
        follower.heading_degrees() - 60
    )
    follower_right = follower.location().neighbor_at_heading(
        follower.heading_degrees() + 60
    )
    further_tiles = []
    for tile in map_update.tiles:
        if tile.cell.coord == follower_forward:
            nearby_tiles.append(f"Forward tile: {AssetId(tile.asset_id).name}")
        elif tile.cell.coord == follower_left:
            nearby_tiles.append(f"Left tile: {AssetId(tile.asset_id).name}")
        elif tile.cell.coord == follower_right:
            nearby_tiles.append(f"Right tile: {AssetId(tile.asset_id).name}")
        elif tile.asset_id in NatureAssetIds() + [
            AssetId.GROUND_TILE_TREE_SNOW
        ] + TreeAssetIds() + [AssetId.GROUND_TILE_PATH]:
            direction = (
                follower.heading_degrees()
                - follower.location().degrees_to_precise(tile.cell.coord)
                - 60
            )
            distance = follower.location().distance_to(tile.cell.coord)
            further_tiles.append(
                f"Tile at heading {direction:.0f} and distance {distance:.1f}: {AssetId(tile.asset_id).name}"
            )
            # Describe tiles not covered in mountains, lakes, or cities.

    # Combine all descriptions
    [header] + prop_descriptions + metadata_descriptions + nearby_tiles
    prompt = (
        header
        + instruction_section
        + "\n"
        + "PROP DESCRIPTIONS\n\t"
        + "\n\t".join(prop_descriptions)
        + "\nTURN_STATE\n\t"
        + turn_state_description
        + "\nMAP DESCRIPTION\n\t"
        + "\n\t".join(metadata_descriptions)
        + "\nNEARBY TILES\n\t"
        + "\n\t".join(nearby_tiles)
        + "\nFURTHER TILES\n\t"
        + "\n\t".join(further_tiles)
    )
    return prompt
