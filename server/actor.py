
from assets import AssetId
from messages.action import Action, Color, ActionType
from messages.rooms import Role
from messages import message_from_server
from messages import message_to_server
from messages import objective, state_sync
from hex import HecsCoord
from queue import Queue
from map_provider import MapProvider, MapType
from card import CardSelectAction
from util import IdAssigner
from datetime import datetime, timedelta
from messages.turn_state import TurnState, GameOverMessage, TurnUpdate

import aiohttp
import asyncio
import dataclasses
import logging
import math
import random
import time
import uuid

class Actor(object):
    def __init__(self, actor_id, asset_id, role, spawn):
        self._actor_id = actor_id
        self._asset_id = asset_id
        self._actions = Queue()
        self._location = spawn
        self._heading_degrees = 0
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
        self._actions.put(action)

    def has_actions(self):
        return not self._actions.empty()

    def location(self):
        return self._location

    def heading_degrees(self):
        return int(self._heading_degrees)

    def state(self):
        return state_sync.Actor(self.actor_id(), self.asset_id(),
                                self._location, self._heading_degrees)

    def peek(self):
        """ Peeks at the next action without consuming it. """
        return self._actions.queue[0]

    def step(self):
        """ Executes & consumes an action from the queue."""
        if not self.has_actions():
            return
        action = self._actions.get()
        self._location = HecsCoord.add(self._location, action.displacement)
        self._heading_degrees += action.rotation

    def drop(self):
        """ Drops an action instead of acting upon it."""
        if not self.has_actions():
            return
        _ = self._actions.get()
