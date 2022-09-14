from ast import Global
from datetime import datetime
from enum import Enum
from server.map_tools import visualize
from server.messages import message_from_server
from server.messages import message_to_server
from server.messages.rooms import Role
from server.messages import objective
from server.remote_table import GetRemote
from server.messages.logs import LogEntryFromIncomingMessage, LogEntryFromOutgoingMessage
from server.messages.tutorials import RoleFromTutorialName
from server.state_machine_driver import StateMachineDriver
from server.state import State
from server.tutorial_state import TutorialGameState
from server.config.config import GlobalConfig

import asyncio
import logging
import orjson
import os
import pathlib
import peewee
from datetime import datetime

import server.schemas.game as game_db
import server.schemas.clients as clients_db
import server.schemas.mturk as mturk_db

logger = logging.getLogger()

class RoomType(Enum):
    NONE = 0
    TUTORIAL = 1
    GAME = 2

class Room(object):
    """ Represents a game room. """
    def __init__(self, name: str, max_players: int, game_id: int, game_record,
                 type: RoomType = RoomType.GAME, tutorial_name: str = ""):
        self._name = name
        self._max_players = max_players
        self._players = []
        self._player_endpoints = []
        self._id = game_id
        self._room_type = type
        self._game_record = game_record
        if self._room_type == RoomType.GAME:
            self._game_record.type = 'game'
            game_state = State(self._id, self._game_record)
        elif self._room_type == RoomType.TUTORIAL:
            if RoleFromTutorialName(tutorial_name) == Role.LEADER:
                self._game_record.type = 'lead_tutorial'
            else:
                self._game_record.type = 'follow_tutorial'
            game_state = TutorialGameState(self._id, tutorial_name, self._game_record)
        else:
            game_state = None
            logger.error("Room started with invalid type NONE.")
        self._state_machine_driver = StateMachineDriver(game_state, self._id)
        self._game_record.save()
        self._update_loop = None
        log_directory = pathlib.Path(game_record.log_directory)
        if not os.path.exists(log_directory):
            logger.warning('Provided log directory does not exist. Game will not be recorded.')
            return
        self._log_directory = log_directory
        messages_from_server_path = pathlib.Path(self._log_directory, 'messages_from_server.jsonl.log')
        self._messages_from_server_log = messages_from_server_path.open('w')
        messages_to_server_path = pathlib.Path(self._log_directory, 'messages_to_server.jsonl.log')
        self._messages_to_server_log = messages_to_server_path.open('w')

        # Write the current server config to the log_directory as config.json.
        with open(pathlib.Path(self._log_directory, 'config.json'), 'w') as f:
            server_config = GlobalConfig()
            if server_config is not None:
                f.write(orjson.dumps(server_config).decode('utf-8'))

        self._map_update_count = 0
    
    def game_record(self):
        return self._game_record

    def add_player(self, ws, role):
        """ Adds a player to the room. """
        if self.is_full():
            raise ValueError("Room is full.")
        state_machine = self._state_machine_driver.state_machine()
        id = state_machine.create_actor(role)
        remote = GetRemote(ws)

        if remote != None:
            remote_record = clients_db.Remote.select().join(mturk_db.Worker, join_type=peewee.JOIN.LEFT_OUTER).where(
                clients_db.Remote.hashed_ip==remote.hashed_ip, 
                clients_db.Remote.remote_port==remote.client_port).get()
            if remote_record is None:
                logger.error(f"Added player with unrecognized remote IP(md5 hash)/Port: {remote.hashed_ip}/{remote.client_port}")
            # If at least one of the players in this game is an mturk worker, mark the game type as "-mturk" (ex "game-mturk", or "follower-tutorial-mturk")
            if remote_record.worker is not None:
                if remote_record.worker.hashed_id != "":
                    if "-mturk" not in self._game_record.type:
                        self._game_record.type += "-mturk"
            if role == Role.LEADER:
                self._game_record.lead_remote = remote_record
                if (remote_record is not None) and (remote_record.assignment is not None):
                    self._game_record.lead_assignment = remote_record.assignment
                    self._game_record.leader = remote_record.worker
            else:
                self._game_record.follow_remote = remote_record
                if (remote_record is not None) and remote_record.assignment is not None:
                    self._game_record.follow_assignment = remote_record.assignment
                    self._game_record.follower = remote_record.worker
            self._game_record.save()
        else:
            logger.warn(f"Error: socket with null remote encountered??")
        self._players.append(id)
        self._player_endpoints.append(ws)
        return id

    def remove_player(self, id, ws):
        """ Removes a player from the room. """
        self._players.remove(id)
        self._player_endpoints.remove(ws)
        self._state_machine_driver.state_machine().free_actor(id)

    def player_endpoints(self):
        return self._player_endpoints

    def number_of_players(self):
        return len(self._players)

    def drain_messages(self, id, messages):
        self._state_machine_driver.drain_messages(id, messages)
        # Log messages
        for message in messages:
            log_message = orjson.dumps(LogEntryFromIncomingMessage(id, message), option=orjson.OPT_NAIVE_UTC | orjson.OPT_PASSTHROUGH_DATETIME, default=datetime.isoformat).decode('utf-8')
            self._messages_to_server_log.write(log_message + "\n")
            logger.info(f"Received message type {message.type} for player {id}.")

    def start(self):
        if self._update_loop is not None:
            return RuntimeError("started Room that is already running.")

        self._update_loop = asyncio.create_task(self._state_machine_driver.run())
        logging.info(f"Room {self.id()} started game.")

    def stop(self):
        if self._update_loop is None:
            return RuntimeError("stopped Room that is not running.")
        logging.info(f"Room /{self.id()} ending game.")
        self._state_machine_driver.end_game()
        if not os.path.exists(self._log_directory):
            return
        self._messages_from_server_log.close()
        self._messages_to_server_log.close()
    
    def done(self):
        return self._state_machine_driver.done()
    
    def has_pending_messages(self):
        return self._state_machine_driver.state_machine().has_pending_messages()

    def desync(self, id):
        self._state_machine_driver.state_machine().desync(id)

    def desync_all(self):
        self._state_machine_driver.state_machine().desync_all()

    def is_full(self):
        """ Returns True if the room is full. """
        return len(self._players) == self._max_players

    def is_empty(self):
        """ Returns True if the room is empty. """
        return len(self._players) == 0

    def state(self, actor_id=-1):
        return self._state_machine_driver.state_machine().state(actor_id)
    
    def selected_cards(self):
        return self._state_machine_driver.state_machine().selected_cards()
    
    def debug_status(self):
        is_done = self.done()
        turn_state = self._state_machine_driver.state_machine().turn_state()

        # Serialize state to json.
        turn_state_json = orjson.dumps(turn_state, option=orjson.OPT_PASSTHROUGH_DATETIME | orjson.OPT_INDENT_2, default=datetime.isoformat).decode('utf-8')

        return {
            'is_done': str(is_done),
            'turn_state': turn_state_json,
        }

    def fill_messages(self, player_id, out_messages):
        """ Returns a MessageFromServer object to send to the indicated player.

            If no message is available, returns None.
        """
        messages = []
        if not self._state_machine_driver.fill_messages(player_id, messages):
            return False
        out_messages.extend(messages)

        for message in messages:
            logger.info(f"Sent message type {message.type} for player {player_id}.")
            log_bytes = orjson.dumps(LogEntryFromOutgoingMessage(player_id, message), option=orjson.OPT_NAIVE_UTC | orjson.OPT_PASSTHROUGH_DATETIME, default=datetime.isoformat).decode('utf-8')
            self._messages_from_server_log.write(log_bytes + "\n")
        return True

    def id(self):
        """ Returns the room id. """
        return self._id

    def name(self):
        """ Returns the room name. """
        return self._name

    def is_synced(self):
        return self._state_machine_driver.state_machine().is_synced()

    def is_synced(self, player_id):
        return self._state_machine_driver.state_machine().is_synced(player_id)