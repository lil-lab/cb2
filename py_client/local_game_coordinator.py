""" This file defines utilities for coordinating and matching local gym environments.

    Each local game has a unique game name, and agent environments use this name to
    find each other. The game coordinator is responsible for matching agents to 

"""

import asyncio
import logging
import pathlib
import pygame
import time
import uuid

from collections import deque
from datetime import datetime, timedelta
from server.actor import Actor
from server.map_tools.visualize import GameDisplay
from server.messages import message_from_server
from server.messages.turn_state import TurnState
from server.messages.objective import ObjectiveMessage
from server.messages.state_sync import StateSync
import server.messages.map_update as map_update

import server.schemas.game as game_db
import server.schemas.cards as card_db
import server.schemas.map as map_db
import server.card as card
import server.state

from py_client.game_endpoint import GameEndpoint
from py_client.game_socket import GameSocket
from server.messages.rooms import Role
from server.state import State
from server.state_machine_driver import StateMachineDriver
from server.util import GetCommitHash

logger = logging.getLogger(__name__)


# Used to manage state machines for local games, each with two agents.
# Hand-wavy intended use pseudocode:
#
#       coordinator = LocalGameCoordinator()
#       game_name = coordinator.CreateGame()
#       # Creating the OpenAI environment implicitly calls JoinGame(game_name).
#       leader_env = gym.make("CerealBar2-v0", render_mode="human", mode=EnvMode.LOCAL, game_name=game_name, coordinator=coordinator)
#       follower_env = gym.make("CerealBar2-v0", render_mode="human", mode=EnvMode.LOCAL, game_name=game_name, coordinator=coordinator)
#       leader = ...
#       follower = ...
#       leader_env_state = leader_env.reset()
#       follower_env_state = follower_env.reset()
#       while True:
#           leader_action = leader(leader_env_state)
#           follower_action = follower(follower_env_state)
#           leader_env_state, leader_reward, leader_done, leader_info = leader_env.step(leader_action)
#           follower_env_state, follower_reward, follower_done, follower_info = follower_env.step(follower_action)
#           if leader_done or follower_done:
#               break
#       # The game is over, so we can clean up the state machine.
#       coordinator.Cleanup()
#
#
# Note that CreateGameFromDatabase() can be used instead of CreateGame() to
# create a game which is initialized from a specific instruction in a recorded
# game.

class LocalSocket(GameSocket):
    def __init__(self, local_coordinator, game_name: str, actor_id: int):
        self.local_coordinator = local_coordinator
        self.game_name = game_name
        self.actor_id = actor_id
        # A list of received messages, in order from oldest to newest. Use like FIFO.
        self.received_messages = deque()

    def send_message(self, message):
        state_machine_driver = self.local_coordinator._state_machine_driver(self.game_name)
        state_machine_driver.drain_messages(self.actor_id, [message])
        time.sleep(0.1)

    def connected(self):
        return self.local_coordinator._game_exists(self.game_name)
    
    def receive_message(self, timeout=timedelta(seconds=60)):
        """ This is a local socket. We don't need to worry about timeouts. No blocking operations. """
        # Give the state machine a chance to run.
        end_time = datetime.utcnow() + timeout
        # Wait until we have at least one message to return.
        logger.info(f"Waiting for packet. {self.actor_id}")
        while datetime.utcnow() < end_time:
            state_machine_driver = self.local_coordinator._state_machine_driver(self.game_name)
            state_machine_driver.fill_messages(self.actor_id, self.received_messages)
            if len(self.received_messages) > 0:
                return self.received_messages.popleft(), ""
            time.sleep(0.1)
        return None, "No messages available."

class LocalGameCoordinator(object):
    def __init__(self, config, render_leader=False, render_follower=False):
        self._game_drivers = {} # Game name -> StateMachineDriver
        self._game_tasks = {} # Game name -> StateMachineDriver asyncio task.
        self._game_endpoints = {} # Game name -> (leader_endpoint, follower_endpoint)
        self._render_leader = render_leader
        self._render_follower = render_follower
        self._config = config
    
    def CreateGame(self):
        """ Creates a new game. Exactly two agents can join this game with JoinGame(). 

            Returns the game name.
        """
        game_name = self._unique_game_name()
        if game_name in self._game_drivers:
            raise Exception(f"Game name {game_name} already exists. This should never happen.")
        room_id = game_name
        # Setup game DB entry.
        game_record = game_db.Game()
        game_id = game_record.id
        game_time = datetime.now().strftime("%Y-%m-%dT%Hh.%Mm.%Ss%z")
        game_name = f"{game_time}_{game_id}_GAME"
        log_directory = pathlib.Path(self._config.record_directory(), game_name)
        log_directory.mkdir(parents=False, exist_ok=False)
        game_record.log_directory = str(log_directory)
        game_record.server_software_commit = GetCommitHash()
        game_record.save()
        state_machine = State(room_id, game_record)
        event_loop = asyncio.get_event_loop()
        self._game_drivers[game_name] = StateMachineDriver(state_machine, room_id)
        self._game_tasks[game_name] = event_loop.create_task(self._game_drivers[game_name].run())
        return game_name
    
    # TODO(sharf): Actually implement this...
    def CreateGameFromDatabase(self, instruction_uuid: str):
        """ Creates a new game from a specific instruction in a recorded game. Exactly two agents can join this game with JoinGame(). 

            Returns the game name.
        """
        game_name = self._unique_game_name()
        if game_name in self._game_drivers:
            raise Exception(f"Game name {game_name} already exists. This should never happen.")
        room_id = game_name
        
        # For cards, take all cards so far and then delete any CardSets().
        state_machine = State.InitializeFromExistingState(room_id, instruction_uuid)

        state_sync = state_machine.state(-1)

        event_loop = asyncio.get_event_loop()
        self._game_drivers[game_name] = StateMachineDriver(state_machine, room_id)
        self._game_tasks[game_name] = event_loop.create_task(self._game_drivers[game_name].run())
        return game_name
    
    def DrawGame(self, game_name):
        # Visualize all state here.
        if game_name not in self._state_machine_driver:
            raise Exception(f"Game {game_name} does not exist.")
        display = GameDisplay(800)
        display.set_config(self._config)
        state_machine = self._state_machine_driver[game_name].state_machine()
        state_sync = state_machine.state(-1)
        display.set_instructions(state_machine._objectives)
        display.set_map(state_machine.map())
        cards = state_machine.cards()
        display.set_props([card.prop() for card in cards])
        display.set_state_sync(state_sync)
        display.draw()
        pygame.display.flip()
        
    def JoinGame(self, game_name):
        """ Joins a game with the given name.
        
            If the game doesn't exist, crashes.
            If the game already has two players, crashes.

            Returns a Game object used to interact with the game.
        """
        # If the game doesn't exist, crash.
        if game_name not in self._game_drivers:
            raise ValueError(f"Game {game_name} doesn't exist. Create it first with CreateGame().")

        # If the game exists, choose role depending on number of players.
        game_driver = self._game_drivers[game_name]
        state_machine = game_driver.state_machine()

        number_players = len(state_machine.player_ids())

        if number_players >= 2:
            raise Exception(f"Game is full! Number of players: {len(state_machine.player_ids())}")

        # If the game has one player, join as leader. Else, follow.
        role = Role.LEADER if number_players == 0 else Role.FOLLOWER
        actor_id = state_machine.create_actor(role)
        render = self._render_leader if role == Role.LEADER else self._render_follower
        game_endpoint = GameEndpoint(LocalSocket(self, game_name, actor_id), self._config, render)
        # Register endpoints for this game so we can initialize them in StartGame().
        if number_players == 0:
            self._game_endpoints[game_name] = (game_endpoint, None)
        else:
            leader = self._game_endpoints[game_name][0]
            self._game_endpoints[game_name] = (leader, game_endpoint)
        return game_endpoint
    
    def StartGame(self, game_name):
        """ Starts a game with the given name. 
        
            The idea is you create a game, then the leader & follower join, then the game begins.
        """
        leader_endpoint, follower_endpoint = self._game_endpoints[game_name]

    def Cleanup(self):
        """ Cleans up any games that have ended. Call this regularly to avoid memory leaks.

            Only deletes a SM if its associated task has ended.
        """
        # list() call is necessary to create a copy. Otherwise we're mutating a
        # list as we iterate through it.
        for game_name in list(self._game_drivers.keys()):
            game_driver = self._game_drivers[game_name]
            if self._game_tasks[game_name].done() and game_driver.state_machine().done():
                logger.info(f"Game {game_name} has ended. Cleaning up.")
                del self._game_tasks[game_name]
                del self._game_drivers[game_name]

    def _unique_game_name(cls):
        """ Generates a random UUID and returns.
        
        UUIDs are 128 bits, you only have to worry about odds of a duplicate
        once you reach ~quintillions of UUIDs generated. Note that I'm not sure
        if this is threadsafe, but some brief research online has me convinced
        this should work.
        
        Mathematical analysis of collision chances:
        https://en.wikipedia.org/wiki/Universally_unique_identifier#Collisions
        """
        return str(uuid.uuid4())
    
    def _state_machine_driver(self, game_name: str):
        if game_name not in self._game_drivers:
            raise ValueError(f"Game {game_name} doesn't exist.")
        
        return self._game_drivers[game_name]
    
    def _game_exists(self, game_name: str):
        return game_name in self._game_drivers
