""" This class defines a set of helper methods to mask game state from the follower's perspective. """

import logging

import copy

from server.messages.map_update import MapUpdate
from server.messages.prop import Prop

from server.actor import Actor

logger = logging.getLogger(__name__)

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

def CoordinateIsVisible(coord, follower_actor, config):
    """  Returns true if the given coordinate should be visible to the given follower with the given config. """
    view_depth = config["fog_end"] / UNITY_COORDINATES_SCALE
    # There's something wrong with orientation... I have to put - 60 everywhere
    # Actor.heading_degrees() (actor.py) is used.
    follower_orientation = follower_actor.heading_degrees() - 60

    # Get the two neighboring cells to the left and right. Special case them.
    neighbor_cells = [
        follower_actor.location().neighbor_at_heading(follower_actor.heading_degrees() - 60),
        follower_actor.location().neighbor_at_heading(follower_actor.heading_degrees() + 60)
    ]
    if coord in neighbor_cells:
        return True

    # Check distance.
    distance = coord.distance_to(follower_actor.location())
    # Add 0.5 to round up to the next hex cell.
    if distance > (view_depth + 0.5):
        return False
    # Special case distance == 0 to avoid weird FOV calculations.
    if distance == 0:
        return True
    # Check FOV. TODO(sharf): Something's not quite right here. Too many tiles are filtered.
    degrees_to = follower_actor.location().degrees_to_precise(coord) % 360
    left = (follower_orientation - FOLLOWER_FOV / 2) % 360
    right = (follower_orientation + FOLLOWER_FOV / 2) % 360
    if left < right:
        return left <= degrees_to <= right
    else:
        return left <= degrees_to or degrees_to <= right

def CensorFollowerMap(map_update, follower_actor, config):
    """ Removes all map tiles which aren't visible to the follower. 

        This is done by defining a circle sector (pie slice). The center (point of the slice) is at the follower's location.
        The arc spans the FOV, at a radius defined by the config fog distance (fog_end).
        
        Args:
            map_update: The map to censor.
            follower_actor: The follower actor. Used to find the actor's location & heading.
            config: The game configuration. Used to determine follower visibility.
    """
    view_depth = config["fog_end"] / UNITY_COORDINATES_SCALE
    # There's something wrong with orientation... I have to put - 60 everywhere
    # Actor.heading_degrees() (actor.py) is used.
    follower_orientation = follower_actor.heading_degrees() - 60

    new_tiles = []
    logger.info(f"Filtering tiles. Follower at {follower_actor.location()} with orientation {follower_orientation} and view depth {view_depth}")
    for tile in map_update.tiles:
        if CoordinateIsVisible(tile.cell.coord, follower_actor, config):
            new_tiles.append(copy.deepcopy(tile))
    map_update_clone = MapUpdate(map_update.rows, map_update.cols, new_tiles, map_update.metadata)
    return map_update_clone

def CensorFollowerProps(props, follower_actor, config):
    """ Removes all props which aren't visible to the follower. 

        This is done by defining a circle sector (pie slice). The center (point of the slice) is at the follower's location.
        The arc spans the FOV, at a radius defined by the config fog distance (fog_end).
        
        Args:
            props: A list of server/messages/props.py Prop objects to filter.
            follower_actor: The follower actor. Used to find the actor's location & heading.
            config: The game configuration. Used to determine follower visibility.
    """
    view_depth = config["fog_end"] / UNITY_COORDINATES_SCALE
    # There's something wrong with orientation... I have to put - 60 everywhere
    # Actor.heading_degrees() (actor.py) is used.
    follower_orientation = follower_actor.heading_degrees() - 60

    new_props = []
    logger.info(f"Filtering props. Follower at {follower_actor.location()} with orientation {follower_orientation} and view depth {view_depth}")
    for prop in props:
        if CoordinateIsVisible(prop.prop_info.location, follower_actor, config):
            new_props.append(copy.deepcopy(prop))
    return new_props

def CensorActors(actors, follower_actor, config):
    """ Removes all actors which aren't visible to the follower. 

        This is done by defining a circle sector (pie slice). The center (point of the slice) is at the follower's location.
        The arc spans the FOV, at a radius defined by the config fog distance (fog_end).
        
        Args:
            actors: A list of server/actor.py Actor objects to filter.
            follower_actor: The follower actor. Used to find the actor's location & heading.
            config: The game configuration. Used to determine follower visibility.
    """
    view_depth = config["fog_end"] / UNITY_COORDINATES_SCALE
    # There's something wrong with orientation... I have to put - 60 everywhere
    # Actor.heading_degrees() (actor.py) is used.
    follower_orientation = follower_actor.heading_degrees() - 60

    new_actors = []
    logger.info(f"Filtering props. Follower at {follower_actor.location()} with orientation {follower_orientation} and view depth {view_depth}")
    for actor in actors:
        if CoordinateIsVisible(actor.location(), follower_actor, config):
            new_actors.append(Actor(actor.actor_id(), actor.asset_id(), actor.role(), actor.location(), False, actor.heading_degrees()))
    return new_actors