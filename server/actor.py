
from .assets import AssetId
from .messages.action import Action, Color, ActionType, Walk, Turn
from .messages.rooms import Role
from .messages import message_from_server
from .messages import message_to_server
from .messages import objective, state_sync
from .hex import HecsCoord
from .map_provider import MapProvider, MapType
from .card import CardSelectAction
from .util import IdAssigner
from .messages.turn_state import TurnState, GameOverMessage, TurnUpdate

import aiohttp
import asyncio
import dataclasses
import logging
import math
import random
import time
import uuid

from queue import Queue
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Actor(object):
    def __init__(self, actor_id, asset_id, role, spawn, realtime=False, spawn_rotation_degrees=0):
        self._actor_id = actor_id
        self._asset_id = asset_id
        self._realtime = realtime
        self._action_start_timestamp = datetime.min
        self._actions = Queue()
        self._location = spawn
        self._heading_degrees = spawn_rotation_degrees
        self._projected_location = spawn
        self._projected_heading = 0
        self._role = role

    def turn():
        pass

    def actor_id(self):
        return self._actor_id

    def asset_id(self):
        return self._asset_id

    def role(self):
        return self._role

    def add_action(self, action):
        # Certain actions aren't cumulative. 
        if action.action_type == ActionType.INIT:
            self._projected_location = action.displacement
            self._projected_heading = action.rotation
        else:
            self._projected_location = HecsCoord.add(self._location, action.displacement)
            self._projected_heading += action.rotation
            self._projected_heading %= 360
        self._actions.put(action)

    def has_actions(self):
        return not self._actions.empty()

    def location(self):
        return self._location

    def heading_degrees(self):
        return int(self._heading_degrees)

    def state(self):
        return state_sync.Actor(self.actor_id(), self.asset_id(),
                                self._location, self._heading_degrees, self._role)

    def peek(self):
        """ Peeks at the next action without consuming it. """
        return self._actions.queue[0]
    
    # This is used for the tutorial automated agent. A realtime actor processes
    # actions in realtime. Instead of actions occuring immediately (and leaving
    # the delay + animation up to the client), they wait in the queue until the
    # duration of the action is complete. This is to orchestrate multiple
    # different actions on different actors/props s.t. they are not all
    # simultaneous.
    def is_realtime(self):
        return self._realtime
    
    def peek_action_done(self):
        return (datetime.now() - self._action_start_timestamp).total_seconds() >= self.peek().duration_s
    
    def WalkForwardsAction(self):
        displacement = HecsCoord.origin().neighbor_at_heading(self._projected_heading)
        return Walk(self.actor_id(), displacement)
    
    def WalkBackwardsAction(self):
        # Note that the displacement is negated on the next line.
        displacement = HecsCoord.origin().neighbor_at_heading(self._projected_heading)
        return Walk(self.actor_id(), displacement.negate())
    
    def TurnLeftAction(self):
        return Turn(self.actor_id(), -60)
    
    def TurnRightAction(self):
        return Turn(self.actor_id(), 60)
    
    def WalkForwards(self):
        self.add_action(self.WalkForwardsAction())
    
    def WalkBackwards(self):
        self.add_action(self.WalkBackwardsAction())

    def TurnLeft(self):
        self.add_action(self.TurnLeftAction())

    def TurnRight(self):
        self.add_action(self.TurnRightAction())

    def step(self):
        """ Executes & consumes an action from the queue."""
        if not self.has_actions():
            return
        action = self._actions.get()
        self._location = HecsCoord.add(self._location, action.displacement)
        self._heading_degrees += action.rotation
        self._heading_degrees %= 360
        self._action_start_timestamp = datetime.now()

    def drop(self):
        """ Drops an action instead of acting upon it."""
        if not self.has_actions():
            return
        _ = self._actions.get()
        self._action_start_timestamp = datetime.now()