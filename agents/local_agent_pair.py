import logging
import time

import fire
import matplotlib.pyplot as plt
import nest_asyncio
import numpy as np
from viztracer import VizTracer

import server.db_tools.db_utils as db_utils
from py_client.endpoint_pair import EndpointPair
from py_client.game_endpoint import Action, Role
from py_client.local_game_coordinator import LocalGameCoordinator
from server.config.config import ReadConfigOrDie
from server.lobbies.open_lobby import OpenLobby
from server.lobby import LobbyInfo, LobbyType

logger = logging.getLogger(__name__)

from agents.config import AgentConfig, AgentType, CreateAgent
from agents.simple_follower import SimpleFollowerConfig


def PlayGame(coordinator, e_uuid="", log_to_db: bool = True, slow: bool = False):
    if len(e_uuid) > 0:
        game_name = coordinator.CreateGameFromDatabase(e_uuid)
    else:
        lobby = OpenLobby(
            LobbyInfo("Test Lobby", LobbyType.OPEN, "Unit test...", 40, 1, False)
        )
        game_name = coordinator.CreateGame(log_to_db=log_to_db, lobby=lobby)

    endpoint_pair = EndpointPair(coordinator, game_name)

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
    endpoint_pair.initialize()
    game_state = endpoint_pair.initial_state()
    while not endpoint_pair.over():
        if slow:
            time.sleep(0.5)
        if game_state.turn_state.turn == Role.LEADER:
            leader_action = leader_agent.choose_action(game_state)
            logger.debug(f"Leader step({leader_action})")
            game_state = endpoint_pair.step(leader_action)
        else:
            logger.debug("=====================")
            follower_action = follower_agent.choose_action(game_state)
            logger.debug(f"Follower step({follower_action})")
            game_state = endpoint_pair.step(follower_action)
    logger.debug(
        f"Game over. Score: {endpoint_pair.score()}, Duration: {endpoint_pair.duration().total_seconds()}"
    )
    coordinator.Cleanup()
    return endpoint_pair.score(), endpoint_pair.duration().total_seconds()


def main(
    config_filepath="server/config/local-covers-config.yaml",
    event_uuid="",
    profile=False,
    num_games=10,
    slow: bool = False,
    log_to_db: bool = False,
):
    nest_asyncio.apply()
    # Disabling most logs improves performance by about 50ms per game.
    logging.basicConfig(level=logging.INFO)
    config = ReadConfigOrDie(config_filepath)
    db_utils.ConnectToDatabase(config)
    scores = []
    durations = []
    coordinator = LocalGameCoordinator(
        config, render_leader=False, render_follower=False
    )
    # If profile=True, play only 1 game, but import viztracer and save the trace to cb2-local.prof.
    if profile:
        with VizTracer(output_file="cb2-local-prof.json", tracer_entries=10000000):
            score, duration = PlayGame(coordinator, event_uuid)
        logger.info(f"Game over. Score: {score}, Duration: {duration}")
        return

    for i in range(num_games):
        logger.info(
            f"========================== STARTING GAME {i} =========================="
        )
        score, duration = PlayGame(
            coordinator, event_uuid, slow=slow, log_to_db=log_to_db
        )
        logger.info(f"Game over. Score: {score}, Duration: {duration}")
        scores.append(score)
        durations.append(duration)
    # Print out the scores.
    logger.info(f"Mean score: {np.mean(scores)}")
    logger.info(f"Mean duration: {np.mean(durations)}")

    # Plot a multi-figure diagram. On the left, scatter plot of game durations &
    # scores. On the right, show a histogram of scores.
    fig, (ax1, ax2) = plt.subplots(1, 2)
    ax1.scatter(durations, scores)
    ax1.set_xlabel("Duration")
    ax1.set_ylabel("Score")
    ax2.hist(scores)
    ax2.set_xlabel("Score")
    ax2.set_ylabel("Frequency")
    plt.show()


if __name__ == "__main__":
    fire.Fire(main)
