"""Integration test which simulates N games between two naive agents."""
import logging
import os
import unittest

import numpy as np
from tqdm import tqdm

from cb2game.agents.config import AgentConfig, AgentType, CreateAgent
from cb2game.agents.simple_follower import SimpleFollowerConfig
from cb2game.pyclient.game_endpoint import Action

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = ""  # Hide pygame welcome message

from cb2game.agents.local_agent_pair import PlayGame
from cb2game.pyclient.local_game_coordinator import LocalGameCoordinator
from cb2game.server.config.config import Config, SetGlobalConfig
from cb2game.server.lobbies.open_lobby import OpenLobby
from cb2game.server.lobby import LobbyInfo, LobbyType
from cb2game.server.schemas.base import (
    ConnectDatabase,
    CreateTablesIfNotExists,
    SetDatabaseForTesting,
)
from cb2game.server.schemas.defaults import ListDefaultTables

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
        logging.getLogger("pyclient.local_game_coordinator").setLevel(logging.WARN)
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
        leader_agent = CreateAgent(
            AgentConfig(
                name="Simple leader",
                comment="Used for testing purposes",
                agent_type=AgentType.SIMPLE_LEADER.name,
            )
        )
        follower_agent = CreateAgent(
            AgentConfig(
                name="Simple follower",
                comment="Used for testing purposes",
                agent_type=AgentType.SIMPLE_FOLLOWER.name,
                simple_follower_config=SimpleFollowerConfig(
                    default_action=Action.ActionCode.INSTRUCTION_DONE.name,
                ),
            )
        )
        for i in tqdm(range(NUMBER_OF_GAMES)):
            score, duration = PlayGame(
                self.coordinator,
                leader_agent,
                follower_agent,
                slow=False,
                log_to_db=False,
            )
            self.scores.append(score)
            self.durations.append(duration)
        # Print out the scores.
        logger.info(f"Mean score: {np.mean(self.scores)}")
        logger.info(f"Mean duration: {np.mean(self.durations)}")
