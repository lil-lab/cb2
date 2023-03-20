from typing import List

from py_client.follower_data_masking import CoordinateIsVisible
from server.actor import Actor
from server.assets import AssetId
from server.config.config import Config
from server.hex import HecsCoord
from server.map_utils import AssetId, NatureAssets, TreeAssets
from server.messages.map_update import MapUpdate
from server.messages.objective import ObjectiveMessage
from server.messages.prop import PropType, PropUpdate
from server.messages.turn_state import TurnState


def DescribeLocationFromActor(location: HecsCoord, actor: Actor) -> str:
    """Returns a string describing the given location from the perspective of the given actor."""
    distance = actor.location().distance_to(location)
    direction = (
        round(
            actor.heading_degrees()
            - actor.location().degrees_to_precise(location)
            - 60,
            1,
        )
        % 360
    )
    return f"distance: {distance} units and heading: {direction} degrees"


def FollowerSystemPrompt() -> str:
    system_prompt = "GAME EXPLANATION: "
    system_prompt += "You are playing a text-based videogame. In this game, you are the FOLLOWER. Your role is to follow the ACTIVE instruction. Move by entering a number of comma-separated 'R', 'L', 'F', and 'B' commands (Right, Left, Forward, and Back). You can also write 'D', to mark an instruction as completed. Each turn, you can only make 10 movements (see TURN_STATE for number of remaining moves). Headings are described in degrees, with positive meaning to the left and negative meaning to the right. You are on a discrete hex grid, each turn is 60 degrees. Example instruction: F,F,F,D. This means move forward 3 times, then marks the instruction as done. You can only use a `d` command once per instruction."
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
                prop.prop_info.location, follower
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
                HecsCoord.from_offset(lake.r, lake.c), follower
            )
            metadata_descriptions.append(
                f"{lake.type.name} lake of size {lake.size} and shape {lake.type.name} at {location_description}."
            )
    for mountain in metadata.mountains:
        if CoordinateIsVisible(
            HecsCoord.from_offset(mountain.r, mountain.c), follower, fog_end
        ):
            location_description = DescribeLocationFromActor(
                HecsCoord.from_offset(mountain.r, mountain.c), follower
            )
            metadata_descriptions.append(
                f"{mountain.type.name} mountain{' (snowy)' if mountain.snowy else ''} at {location_description}."
            )
    for city in metadata.cities:
        if CoordinateIsVisible(
            HecsCoord.from_offset(city.r, city.c), follower, fog_end
        ):
            location_description = DescribeLocationFromActor(
                HecsCoord.from_offset(city.r, city.c), follower
            )
            metadata_descriptions.append(
                f"City of size {city.size} at {location_description}."
            )
    for outpost in metadata.outposts:
        if CoordinateIsVisible(
            HecsCoord.from_offset(outpost.r, outpost.c), follower, fog_end
        ):
            location_description = DescribeLocationFromActor(
                HecsCoord.from_offset(outpost.r, outpost.c), follower
            )
            metadata_descriptions.append(f"Outpost at {location_description}.")

    # If provided, and if visible, describe the leader.
    if leader:
        if CoordinateIsVisible(leader.location(), follower, fog_end):
            leader_location = DescribeLocationFromActor(leader.location(), follower)
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
        elif tile.asset_id in NatureAssets() + [
            AssetId.GROUND_TILE_TREE_SNOW
        ] + TreeAssets() + [AssetId.GROUND_TILE_PATH]:
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
