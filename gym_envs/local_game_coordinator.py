""" This file defines utilities for coordinating and matching local gym environments.

    Each local game has a unique game name, and agent environments use this name to
    find each other. The game coordinator is responsible for matching agents to 

"""

import logging
import pathlib
import uuid

from datetime import datetime

import server.schemas.game as game_db

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
# Note that CreateGameFromDatabase() can be used instead of CreateGame() to
# create a game which is initialized from a specific instruction in a recorded
# game.
class LocalGameCoordinator(object):
    def __init__(self):
        self._game_drivers = {} # Game name -> StateMachineDriver
    
    def CreateGame(self):
        """ Creates a new game. Exactly two agents can join this game with JoinGame(). 

            Returns the game name.
        """
        game_name = self._unique_game_name()
        room_id = game_name
        # Setup game DB entry.
        game_record = game_db.Game()
        game_id = game_record.id
        game_time = datetime.now().strftime("%Y-%m-%dT%Hh.%Mm.%Ss%z")
        game_name = f"{game_time}_{game_id}_GAME"
        log_directory = pathlib.Path(self._base_log_directory, game_name)
        log_directory.mkdir(parents=False, exist_ok=False)
        game_record.log_directory = str(log_directory)
        game_record.server_software_commit = GetCommitHash()
        game_record.save()
        state_machine = State(room_id, game_record)
        self._game_drivers[game_name] = StateMachineDriver(state_machine, room_id)
        return game_name
    
    # TODO(sharf): Actually implement this...
    def CreateGameFromDatabase(self, game, game_id: int, instruction_uuid: str):
        ...
    
    def JoinGame(self, game_name):
        """ Joins a game with the given name.
        
            If the game doesn't exist, crashes.
            If the game already has two players, crashes.

            Returns a player ID unique to this game which can be used to interact with the game.
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
        return state_machine.create_actor(Role.LEADER if number_players == 0 else Role.FOLLOWER)

    def Cleanup(self):
        """ Cleans up any games that have ended. Call this regularly to avoid memory leaks. """
        # list() call is necessary to create a copy. Otherwise we're mutating a
        # list as we iterate through it.
        for game_name in list(self._game_drivers.keys()):
            game_driver = self._game_drivers[game_name]
            if game_driver.state_machine().done():
                logger.info(f"Game {game_name} has ended. Cleaning up.")
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
    