from messages import message_from_server
from messages import message_to_server
from messages.rooms import Role
from messages import objective
from state import State

import asyncio
import logging
from datetime import datetime


class Room(object):
    """ Represents a game room. """

    def __init__(self, name, max_players, game_id, password=None):
        self._name = name
        self._max_players = max_players
        self._players = []
        self._player_endpoints = []
        self._id = game_id
        self._game_state = State(self._id)
        self._password = password
        self._update_loop = None

    def add_player(self, ws, role):
        """ Adds a player to the room. """
        if self.is_full():
            raise ValueError("Room is full.")
        id = self._game_state.create_actor(role)
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

    def handle_objective(self, id, objective):
        self._game_state.handle_objective(id, objective)
    
    def handle_objective_complete(self, id, objective_complete):
        self._game_state.handle_objective_complete(id, objective_complete)
    
    def handle_turn_complete(self, id, turn_complete):
        self._game_state.handle_turn_complete(id, turn_complete)

    def handle_packet(self, id, message):
        if message.type == message_to_server.MessageType.ACTIONS:
            logging.info(f'Actions received. Room: {self.id()}')
            for action in message.actions:
                logging.info(f'{action.id}:{action.displacement}')
                self.handle_action(id, action)
        elif message.type == message_to_server.MessageType.OBJECTIVE:
            logging.info(
                f'Objective received. Room: {self.id()}, Text: {message.objective.text}')
            self.handle_objective(id, message.objective)
        elif message.type == message_to_server.MessageType.OBJECTIVE_COMPLETED:
            logging.info(
                f'Objective Compl received. Room: {self.id()}, Text: {message.objective_complete.uuid}')
            self.handle_objective_complete(id, message.objective_complete)
        elif message.type == message_to_server.MessageType.TURN_COMPLETE:
            logging.info(f'Turn Complete received. Room: {self.id()}')
            self.handle_turn_complete(id, message.turn_complete)
        elif message.type == message_to_server.MessageType.STATE_SYNC_REQUEST:
            logging.info(
                f'Sync request recvd. Room: {self.id()}, Player: {id}')
            self.desync(id)
        else:
            logging.warn(f'Received unknown packet type: {message.type}')

    def start(self):
        if self._update_loop is not None:
            return RuntimeError("started Room that is already running.")

        self._update_loop = asyncio.create_task(self._game_state.update())
        logging.info(f"Room {self.id()} started game.")

    def stop(self):
        if self._update_loop is None:
            return RuntimeError("stopped Room that is not running.")
        logging.info(f"Room {self.id()} ending game.")
        self._game_state.end_game()
    
    def done(self):
        return self._game_state.done()
    
    def has_pending_messages(self):
        return self._game_state.has_pending_messages()

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
    
    def debug_status(self):
        is_done = self.done()
        game_state = self._game_state.state(-1)
        map = self._game_state.map()
        turn_state = self._game_state.turn_state()
        return {
            'is_done': str(is_done),
            'game_state': game_state.to_json(),
            'map': map.to_json(),
            'turn_state': turn_state.to_json(),
        }

    def drain_message(self, player_id):
        """ Returns a MessageFromServer object to send to the indicated player.

            If no message is available, returns None.
        """
        if not self._game_state.is_synced(player_id):
            state_sync = self._game_state.sync_message_for_transmission(
                player_id)
            msg = message_from_server.StateSyncFromServer(state_sync)
            return msg

        actions = self._game_state.drain_actions(player_id)
        if len(actions) > 0:
            logging.info(
                f'Room {self.id()} drained {len(actions)} actions for player_id {player_id}')
            msg = message_from_server.ActionsFromServer(actions)
            return msg

        objectives = self._game_state.drain_objectives(player_id)
        if len(objectives) > 0:
            logging.info(
                f'Room {self.id()} drained {len(objectives)} texts for player_id {player_id}')
            msg = message_from_server.ObjectivesFromServer(objectives)
            return msg
        
        turn_state = self._game_state.drain_turn_state(player_id)
        if not turn_state is None:
            logging.info(
                f'Room {self.id()} drained ts {turn_state} for player_id {player_id}')
            msg = message_from_server.GameStateFromServer(turn_state)
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
