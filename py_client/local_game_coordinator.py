""" This file defines utilities for coordinating and matching local gym environments.

    Each local game has a unique game name, and agent environments use this name to
    find each other. The game coordinator is responsible for matching agents to

"""

import logging
import sys
import uuid
from collections import deque
from datetime import datetime, timedelta

import pygame

import server.schemas.game as game_db
from py_client.game_endpoint import GameEndpoint
from py_client.game_socket import GameSocket
from server.map_tools.visualize import GameDisplay
from server.messages.rooms import Role
from server.messages.tutorials import (
    FOLLOWER_TUTORIAL,
    LEADER_TUTORIAL,
    RoleFromTutorialName,
)
from server.state import State
from server.state_machine_driver import StateMachineDriver
from server.tutorial_state import TutorialGameState
from server.util import GetCommitHash

logger = logging.getLogger(__name__)


# pylint: disable=protected-access
class LocalSocket(GameSocket):
    """Used to manage state machines for local games, each with two agents.

    Note that CreateGameFromDatabase() can be used instead of CreateGame() to
    create a game which is initialized from a specific instruction in a recorded
    game.

    """

    def __init__(self, local_coordinator, game_name: str, actor_id: int):
        self.local_coordinator = local_coordinator
        self.game_name = game_name
        self.actor_id = actor_id
        # A list of received messages, in order from oldest to newest. Use like FIFO.
        self.received_messages = deque()

    def send_message(self, message):
        state_machine_driver = self.local_coordinator._state_machine_driver(
            self.game_name
        )
        state_machine_driver.drain_messages(self.actor_id, [message])
        self.local_coordinator.StepGame(self.game_name)

    def connected(self):
        return self.local_coordinator._game_exists(self.game_name)

    def receive_message_nowait(self):
        ...

    def receive_message(self, timeout=timedelta(seconds=60)):
        """This is a local socket. We don't need to worry about timeouts. No blocking operations."""
        # Give the state machine a chance to run.
        end_time = datetime.utcnow() + timeout
        # Wait until we have at least one message to return.
        while datetime.utcnow() < end_time:
            self.local_coordinator.StepGame(self.game_name)
            state_machine_driver = self.local_coordinator._state_machine_driver(
                self.game_name
            )
            state_machine_driver.fill_messages(self.actor_id, self.received_messages)
            if len(self.received_messages) > 0:
                return self.received_messages.popleft(), ""
        return None, "No messages available."


# pylint: enable=protected-access


class LocalGameCoordinator:
    """Used for starting local games.

    Can run multiple simulated games at once, each with two agents.
    Can start games from a specific instruction in a recorded game.

    """

    def __init__(
        self, config, render_leader: bool = False, render_follower: bool = False
    ):
        self._game_drivers = {}  # Game name -> StateMachineDriver
        self._game_endpoints = {}  # Game name -> (leader_endpoint, follower_endpoint)
        self._render_leader = render_leader
        self._render_follower = render_follower
        self._config = config

    def CreateGame(self, log_to_db: bool = True, realtime_actions: bool = False):
        """Creates a new game. Exactly two agents can join this game with JoinGame().

        Returns the game name.
        """
        if realtime_actions and "unittest" not in sys.modules:
            logger.warning(
                " ".join(
                    [
                        "Warning, realtime actions are intended for unit tests.",
                        "Enabling them in self-play will cause the game to run very",
                        "slowly as the state machine waits for each animation to",
                        "complete.",
                    ]
                )
            )
        game_name = self._unique_game_name()
        if game_name in self._game_drivers:
            raise Exception(
                f"Game name {game_name} already exists. This should never happen."
            )
        room_id = game_name
        # Setup game DB entry.
        if log_to_db:
            game_record = game_db.Game()
            game_id = game_record.id
            game_time = datetime.now().strftime("%Y-%m-%dT%Hh.%Mm.%Ss%z")
            game_name = f"{game_time}_{game_id}_GAME"
            game_record.server_software_commit = GetCommitHash()
            game_record.type = "local-simulated|0|simulated"
            game_record.save()
        else:
            game_record = None
        state_machine = State(
            room_id, game_record, log_to_db=log_to_db, realtime_actions=False
        )
        self._game_drivers[game_name] = StateMachineDriver(state_machine, room_id)
        return game_name

    def CreateGameFromDatabase(self, instruction_uuid: str):
        """Creates a new game from a specific instruction in a recorded game.

        Exactly two agents can join this game with JoinGame().
        Returns the game name.
        """
        game_name = self._unique_game_name()
        if game_name in self._game_drivers:
            raise Exception(
                f"Game name {game_name} already exists. This should never happen."
            )
        room_id = game_name

        # For cards, take all cards so far and then delete any CardSets().
        state_machine, reason = State.InitializeFromExistingState(
            room_id, instruction_uuid, realtime_actions=False
        )
        assert (
            state_machine is not None
        ), f"Failed to init from instr {instruction_uuid}: {reason}"
        state_machine.state(-1)

        self._game_drivers[game_name] = StateMachineDriver(state_machine, room_id)
        return game_name

    def CreateLeaderTutorial(self, realtime: bool = True):
        """Creates a new game. Exactly two agents can join this game with JoinGame().

        Returns the game name.
        """
        return self._CreateTutorial(LEADER_TUTORIAL, realtime)

    def CreateFollowerTutorial(self, realtime: bool = True):
        """Creates a new game. Exactly two agents can join this game with JoinGame().

        Returns the game name.
        """
        return self._CreateTutorial(FOLLOWER_TUTORIAL, realtime)

    def _CreateTutorial(self, tutorial_name: str, realtime: bool):
        """Creates a tutorial game. One-player only.

        Returns the game name.
        """
        game_name = self._unique_game_name()
        if game_name in self._game_drivers:
            raise Exception(
                f"Game name {game_name} already exists. This should never happen."
            )
        room_id = game_name
        role = RoleFromTutorialName(tutorial_name)
        opposite_role = Role.FOLLOWER if role == Role.LEADER else Role.LEADER
        # Setup game DB entry.
        game_record = game_db.Game()
        game_id = game_record.id
        game_time = datetime.now().strftime("%Y-%m-%dT%Hh.%Mm.%Ss%z")
        game_name = f"{game_time}_{game_id}_GAME"
        game_record.server_software_commit = GetCommitHash()
        game_record.type = "local-simulated|0|tutorial"
        game_record.save()
        # The value
        state_machine = TutorialGameState(room_id, tutorial_name, game_record, realtime)
        self._game_endpoints[game_name] = (None, None)
        self._game_drivers[game_name] = StateMachineDriver(state_machine, room_id)
        return game_name

    def DrawGame(self, game_name):
        """Draws the game state to the screen using pygame."""
        if game_name not in self._game_drivers:
            raise Exception(f"Game {game_name} does not exist.")
        display = GameDisplay(800)
        display.set_config(self._config)
        state_machine = self._game_drivers[game_name].state_machine()
        state_sync = state_machine.state(-1)
        # pylint: disable=protected-access
        display.set_instructions(state_machine._objectives)
        # pylint: enable=protected-access
        display.set_map(state_machine.map())
        cards = state_machine.cards()
        display.set_props([card.prop() for card in cards])
        display.set_state_sync(state_sync)
        display.draw()
        pygame.display.flip()

    def JoinTutorial(self, game_name, role: Role):
        """Joins a tutorial with the given name.

        If the game doesn't exist, crashes.

        Returns a Game object used to interact with the game.
        """
        # If the game doesn't exist, crash.
        if game_name not in self._game_drivers:
            raise ValueError(
                f"Game {game_name} doesn't exist. Create it first with CreateGame()."
            )

        game_driver = self._game_drivers[game_name]
        state_machine = game_driver.state_machine()

        number_players = len(state_machine.player_ids())

        if number_players != 1:
            raise Exception(
                f"Game is not ready for player! Number of players: {len(state_machine.player_ids())}"
            )

        # If the game has one player, join as leader. Else, follow.
        actor_id = state_machine.create_actor(role)
        render = self._render_leader if role == Role.LEADER else self._render_follower
        game_endpoint = GameEndpoint(
            LocalSocket(self, game_name, actor_id), self._config, render
        )
        # Register endpoints for this game so we can initialize them in StartGame().
        if role == Role.LEADER:
            self._game_endpoints[game_name] = (game_endpoint, None)
        else:
            self._game_endpoints[game_name] = (None, game_endpoint)
        return game_endpoint

    def JoinGame(self, game_name):
        """Joins a game with the given name.

        If the game doesn't exist, crashes.
        If the game already has two players, crashes.

        Returns a Game object used to interact with the game.
        """
        # If the game doesn't exist, crash.
        if game_name not in self._game_drivers:
            raise ValueError(
                f"Game {game_name} doesn't exist. Create it first with CreateGame()."
            )

        # If the game exists, choose role depending on number of players.
        game_driver = self._game_drivers[game_name]
        state_machine = game_driver.state_machine()

        number_players = len(state_machine.player_ids())

        if number_players >= 2:
            raise Exception(
                f"Game is full! Number of players: {len(state_machine.player_ids())}"
            )

        # If the game has one player, join as leader. Else, follow.
        role = Role.LEADER if number_players == 0 else Role.FOLLOWER
        actor_id = state_machine.create_actor(role)
        render = self._render_leader if role == Role.LEADER else self._render_follower
        game_endpoint = GameEndpoint(
            LocalSocket(self, game_name, actor_id), self._config, render
        )
        # Register endpoints for this game so we can initialize them in StartGame().
        if number_players == 0:
            self._game_endpoints[game_name] = (game_endpoint, None)
        else:
            leader = self._game_endpoints[game_name][0]
            self._game_endpoints[game_name] = (leader, game_endpoint)
        return game_endpoint

    def StepGame(self, game_name):
        """Runs one iteration of the game state machine."""
        game_driver = self._state_machine_driver(game_name)
        game_driver.step()

    def TickCount(self, game_name):
        """Returns the number of ticks that have passed in the game."""
        return self._state_machine_driver(game_name).state_machine().tick_count()

    def Cleanup(self):
        """Cleans up any games that have ended. Call this regularly to avoid memory leaks."""
        # list() call is necessary to create a copy. Otherwise we're mutating a
        # list as we iterate through it.
        for game_name in list(self._game_drivers.keys()):
            game_driver = self._game_drivers[game_name]
            if game_driver.state_machine().done():
                logger.info(f"Game {game_name} has ended. Cleaning up.")
                game_driver.state_machine().on_game_over()
                del self._game_drivers[game_name]

    @staticmethod
    def _unique_game_name():
        """Generates a random UUID and returns.

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
