from messages import message_from_server
from state import State

import asyncio
from datetime import datetime


class Room(object):
    """ Represents a game room. """

    def __init__(self, name, max_players, game_id, password=None):
        self._name = name
        self._max_players = max_players
        self._players = []
        self._player_endpoints = []
        self._id = game_id
        self._game_state = State()
        self._password = password
        self._update_loop = None

    def add_player(self, ws):
        """ Adds a player to the room. """
        if self.is_full():
            raise ValueError("Room is full.")
        id = self._game_state.create_actor()
        self._players.append(id)
        self._player_endpoints.append(ws)
        return id

    def remove_player(self, id, ws):
        """ Removes a player from the room. """
        self._players.remove(id)
        self._player_endpoints.remove(ws)
        self._game_state.free_actor(id)

    def player_endpoints(self):
        return self._player_endpoints

    def number_of_players(self):
        return len(self._players)

    def handle_action(self, id, action):
        self._game_state.handle_action(id, action)

    def start(self):
        if self._update_loop is not None:
            return RuntimeError("started Room that is already running.")
        self._update_loop = asyncio.create_task(self._game_state.update())

    def stop(self):
        if self._update_loop is None:
            return RuntimeError("stopped Room that is not running.")
        self._game_state.end_game()

    def desync(self, id):
        self._game_state.desync(id)

    def desync_all(self):
        self._game_state.desync_all()

    def is_full(self):
        """ Returns True if the room is full. """
        return len(self._players) == self._max_players

    def is_empty(self):
        """ Returns True if the room is empty. """
        return len(self._players) == 0

    def map(self):
        return self._game_state.map()

    def cards(self):
        return self._game_state.cards()

    def state(self, actor_id=-1):
        return self._game_state.state(actor_id)

    def drain_message(self, player_id):
        """ Returns a MessageFromServer object to send to the indicated player.

            If no message is available, returns None.
        """
        if not self._game_state.is_synced(player_id):
            state_sync = self._game_state.sync_message_for_transmission(
                player_id)
            msg = message_from_server.MessageFromServer(datetime.now(
            ), message_from_server.MessageType.STATE_SYNC, None, None, state_sync, None)
            return msg

        actions = self._game_state.drain_actions(player_id)
        if len(actions) > 0:
            msg = message_from_server.MessageFromServer(
                datetime.now(), message_from_server.MessageType.ACTIONS, actions, None, None, None)
            return msg

        # Nothing to send.
        return None

    def id(self):
        """ Returns the room id. """
        return self._id

    def name(self):
        """ Returns the room name. """
        return self._name

    def is_synced(self):
        return self._game_state.is_synced()

    def is_synced(self, player_id):
        return self._game_state.is_synced(player_id)

    async def update(self):
        await self._game_state.update()
