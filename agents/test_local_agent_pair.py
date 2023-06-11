"""Integration test which simulates N games between two naive agents."""
import logging
import os
import unittest

import numpy as np
from tqdm import tqdm

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = ""  # Hide pygame welcome message

from agents.local_agent_pair import PlayGame
from py_client.local_game_coordinator import LocalGameCoordinator
from server.config.config import Config, SetGlobalConfig
from server.lobbies.open_lobby import OpenLobby
from server.lobby import LobbyInfo, LobbyType
from server.schemas.base import (
    ConnectDatabase,
    CreateTablesIfNotExists,
    SetDatabaseForTesting,
)
from server.schemas.defaults import ListDefaultTables

logger = logging.getLogger(__name__)

# If this unit test is taking too long, you can lower the number of games
# played. More games will give you better test coverage, but will take longer to
# run.
NUMBER_OF_GAMES = 3


class RandomRealtimeLocalSelfPlayTest(unittest.TestCase):
    """Runs integration tests on the state machine.

    Uses the pyclient local self-play API.
    """

    def setUp(self):
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("py_client.local_game_coordinator").setLevel(logging.WARN)
        self.config = Config(
            card_covers=True,
            comment="Simple agent pair local self play test.",
        )
        lobby = OpenLobby(
            LobbyInfo("Test Lobby", LobbyType.OPEN, "Unit test...", 40, 1, False)
        )
        SetGlobalConfig(self.config)
        # In-memory db for test validation.
        SetDatabaseForTesting()
        ConnectDatabase()
        CreateTablesIfNotExists(ListDefaultTables())
        self.coordinator = LocalGameCoordinator(self.config)
        self.scores = []
        self.durations = []

    def test_pair(self):
        """Runs a set of games between two naive agents."""
        for i in tqdm(range(NUMBER_OF_GAMES)):
            score, duration = PlayGame(self.coordinator, slow=False, log_to_db=False)
            self.scores.append(score)
            self.durations.append(duration)
        # Print out the scores.
        logger.info(f"Mean score: {np.mean(self.scores)}")
        logger.info(f"Mean duration: {np.mean(self.durations)}")
