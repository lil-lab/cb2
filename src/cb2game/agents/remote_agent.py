"""Connects to a remote server from the command line and plays a game using the specified agent."""
import logging
import time
from datetime import timedelta

import fire

from cb2game.agents.agent import Agent
from cb2game.agents.config import CreateAgent, ReadAgentConfigOrDie
from cb2game.pyclient.game_endpoint import Action
from cb2game.pyclient.remote_client import RemoteClient
from cb2game.server.messages.rooms import Role
from cb2game.server.util import PackageRoot

logger = logging.getLogger(__name__)


def PlayRemoteGame(
    host: str,  # "https://cb2.ai"
    agent: Agent,
    render: bool = False,
    lobby: str = "bot-sandbox",
    pause_per_turn: float = 0,
):
    # Create client and connect to server.
    client = RemoteClient(host, render, lobby_name=lobby)
    connected, reason = client.Connect()
    assert connected, f"Unable to connect: {reason}"

    queue_type = RemoteClient.QueueType.NONE
    if agent.role() == Role.LEADER:
        queue_type = RemoteClient.QueueType.LEADER_ONLY
    elif agent.role() == Role.FOLLOWER:
        queue_type = RemoteClient.QueueType.FOLLOWER_ONLY
    else:
        raise Exception(f"Invalid role: {agent.role()}")

    # Wait in the queue for a game to start.
    game, reason = client.JoinGame(
        timeout=timedelta(minutes=5),
        queue_type=queue_type,
    )
    assert game is not None, f"Unable to join game: {reason}"

    game_state = game.initial_state()

    if agent.role() == Role.FOLLOWER:
        # Leader's turn first. Wait for follower turn by executing a noop.
        action = Action.NoopAction()
        game_state = game.step(action)

    while not game.over():
        if pause_per_turn > 0:
            time.sleep(pause_per_turn)
        action = agent.choose_action(game_state)
        logger.info(f"step({action})")
        game_state = game.step(action)


def main(
    host,
    render=False,
    lobby="bot-sandbox",
    pause_per_turn=0,
    agent_config_filepath: str = (PackageRoot() / "agents/simple_follower.yaml"),
):
    """Connects to a remote server from the command line and plays a game using the specified agent."""
    agent_config = ReadAgentConfigOrDie(agent_config_filepath)
    agent = CreateAgent(agent_config)
    PlayRemoteGame(
        host,
        agent,
        render,
        lobby,
        pause_per_turn,
    )


if __name__ == "__main__":
    fire.Fire(main)
