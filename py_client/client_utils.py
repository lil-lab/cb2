from typing import List

from py_client.follower_data_masking import CoordinateIsVisible
from server.actor import Actor
from server.assets import AssetId
from server.config.config import Config
from server.hex import HecsCoord
from server.messages.map_update import MapUpdate
from server.messages.objective import ObjectiveMessage
from server.messages.prop import PropType, PropUpdate


def DescribeMap(
    map_update: MapUpdate,
    prop_update: PropUpdate,
    instructions: List[ObjectiveMessage],
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

    header += instruction_section

    header += "You are playing as the FOLLOWER. Your role is to follower the ACTIVE instruction. Move by entering any number of 'R', 'L', 'F', and 'B' commands (Right, Left, Forward, and Back). You can also write 'D', to mark an instruction as completed. Headings are described in degrees, with positive meaning to the left and negative meaning to the right. You are on a discrete hex grid, each turn is 60 degrees. \n"

    # Describe the props
    prop_descriptions = []
    for prop in prop_update.props:
        if prop.prop_type == PropType.CARD:
            distance = follower.location().distance_to(prop.prop_info.location)
            direction = (
                follower.heading_degrees()
                - follower.location().degrees_to_precise(prop.prop_info.location)
                - 60
            )
            # Only show shape, color, count for selected cards.
            if prop.card_init.selected:
                prop_descriptions.append(
                    f"Selected card at distance {distance:.1f}, and heading {direction:.0f}. Shape {prop.card_init.shape.name}, color {prop.card_init.color.name}, count {prop.card_init.count}"
                )
            else:
                prop_descriptions.append(
                    f"Card at distance {distance:.1f} and heading {direction:.0f}"
                )
    # Describe the map metadata
    metadata = map_update.metadata
    metadata_descriptions = []
    for lake in metadata.lakes:
        if CoordinateIsVisible(
            HecsCoord.from_offset(lake.r, lake.c), follower, fog_end
        ):
            distance = follower.location().distance_to(
                HecsCoord.from_offset(lake.r, lake.c)
            )
            direction = (
                follower.heading_degrees()
                - follower.location().degrees_to_precise(
                    HecsCoord.from_offset(lake.r, lake.c)
                )
                - 60
            )
            metadata_descriptions.append(
                f"{lake.type.name} lake of size {lake.size} and shape {lake.type.name} at heading {direction:.0f} and distance {distance:.1f}"
            )
    for mountain in metadata.mountains:
        if CoordinateIsVisible(
            HecsCoord.from_offset(mountain.r, mountain.c), follower, fog_end
        ):
            distance = follower.location().distance_to(
                HecsCoord.from_offset(mountain.r, mountain.c)
            )
            direction = (
                follower.heading_degrees()
                - follower.location().degrees_to_precise(
                    HecsCoord.from_offset(mountain.r, mountain.c)
                )
                - 60
            )
            metadata_descriptions.append(
                f"{mountain.type.name} mountain{' (snowy)' if mountain.snowy else ''} at heading {direction:.0f} and distance {distance:.1f}"
            )
    for city in metadata.cities:
        if CoordinateIsVisible(
            HecsCoord.from_offset(city.r, city.c), follower, fog_end
        ):
            distance = follower.location().distance_to(
                HecsCoord.from_offset(city.r, city.c)
            )
            direction = (
                follower.heading_degrees()
                - follower.location().degrees_to_precise(
                    HecsCoord.from_offset(city.r, city.c)
                )
                - 60
            )
            metadata_descriptions.append(
                f"City of size {city.size} at heading {direction:.0f} and distance {distance:.1f}"
            )
    for outpost in metadata.outposts:
        if CoordinateIsVisible(
            HecsCoord.from_offset(outpost.r, outpost.c), follower, fog_end
        ):
            distance = follower.location().distance_to(
                HecsCoord.from_offset(outpost.r, outpost.c)
            )
            direction = (
                follower.heading_degrees()
                - follower.location().degrees_to_precise(
                    HecsCoord.from_offset(outpost.r, outpost.c)
                )
                - 60
            )
            metadata_descriptions.append(
                f"Outpost at heading {direction:.0f} and distance {distance:.1f}"
            )

    # If provided, and if visible, describe the leader.
    if leader:
        if CoordinateIsVisible(leader.location(), follower, fog_end):
            distance = follower.location().distance_to(leader.location())
            direction = (
                follower.heading_degrees()
                - follower.location().degrees_to_precise(leader.location())
                - 60
            )
            metadata_descriptions.append(
                f"Leader at heading {direction:.0f} and distance {distance:.1f}"
            )

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
    for tile in map_update.tiles:
        if tile.cell.coord == follower_forward:
            nearby_tiles.append(f"Forward tile: {AssetId(tile.asset_id).name}")
        elif tile.cell.coord == follower_left:
            nearby_tiles.append(f"Left tile: {AssetId(tile.asset_id).name}")
        elif tile.cell.coord == follower_right:
            nearby_tiles.append(f"Right tile: {AssetId(tile.asset_id).name}")

    # Combine all descriptions
    [header] + prop_descriptions + metadata_descriptions + nearby_tiles
    prompt = (
        header
        + "PROP DESCRIPTIONS\n\t"
        + "\n\t".join(prop_descriptions)
        + "\nMAP DESCRIPTION\n\t"
        + "\n\t".join(metadata_descriptions)
        + "\nNEARBY TILES\n\t"
        + "\n\t".join(nearby_tiles)
    )
    return prompt
