# Re-creation of py_client/demos/local_self_play.py using the OpenAI gym.
import asyncio
import fire
import logging
import matplotlib
import matplotlib.pyplot as plt
import nest_asyncio
import numpy as np
import pygame
import threading
import gym

from math import degrees
from py_client.remote_client import RemoteClient
from py_client.game_endpoint import LeadAction, FollowAction, LeadFeedbackAction, Role
from py_client.demos.follower_client import *
from py_client.demos.routing_leader_client import *
from py_client.local_game_coordinator import LocalGameCoordinator
from py_client.endpoint_pair import EndpointPair
from envs.cb2 import CerealBar2Env, EnvMode

from server.config.config import ReadConfigOrDie
import server.db_tools.db_utils as db_utils

from collections import deque
from datetime import timedelta
from random import choice

from time import sleep

from server.map_provider import MAP_HEIGHT, MAP_WIDTH

logger = logging.getLogger(__name__)

class PathfindingLeader(threading.Thread):
    def __init__(self):
        super().__init__()
        self.exc = None

    def get_action(self, map, cards, turn_state, instructions, actors, feedback):
        if turn_state.turn != Role.LEADER:
            return LeadFeedbackAction(LeadFeedbackAction.ActionCode.NONE)
        if has_instruction_available(instructions):
            # If the follower already has something to do, just end the turn.
            return LeadAction(LeadAction.ActionCode.END_TURN)
        (leader, follower) = actors
        closest_card = get_next_card(cards, follower)
        if closest_card is None:
            # Just have the follower make random moves, hope something happens...
            return LeadAction(LeadAction.ActionCode.SEND_INSTRUCTION, "random, random, random, random, random, random")
        instruction = get_instruction_for_card(closest_card, follower, map, None, cards)
        logger.info(f"Lead sending: {instruction}")
        return LeadAction(LeadAction.ActionCode.SEND_INSTRUCTION, instruction=instruction)

class NaiveFollower(threading.Thread):
    def __init__(self):
        super().__init__()
        self.instructions_processed = set()
        self.actions = []
        self.exc = None
    
    def get_action(self, map, cards, turn_state, instructions, actors, feedback):
        if len(self.actions) == 0:
            active_instruction = get_active_instruction(instructions)
            actions = []
            if active_instruction is not None:
                actions = actions_from_instruction(active_instruction.text)
            else:
                raise Exception(f"No active instruction. Instructions: {instructions}")
            if len(actions) == 0:
                action_codes = [FollowAction.ActionCode.FORWARDS, FollowAction.ActionCode.BACKWARDS, FollowAction.ActionCode.TURN_LEFT, FollowAction.ActionCode.TURN_RIGHT]
                actions = [FollowAction(random.choice(action_codes)) for _ in range(5)]
            self.actions.extend(actions)
            if active_instruction is not None:
                self.actions.append(FollowAction(FollowAction.ActionCode.INSTRUCTION_DONE, active_instruction.uuid))
                self.instructions_processed.add(active_instruction.uuid)
        if len(self.actions) > 0:
            action = self.actions[0]
            self.actions.pop(0)
            return action
        else:
            # Choose a random action.
            action_codes = [FollowAction.ActionCode.FORWARDS, FollowAction.ActionCode.BACKWARDS, FollowAction.ActionCode.TURN_LEFT, FollowAction.ActionCode.TURN_RIGHT]
            action = FollowAction(random.choice(action_codes))
            return action

def PlayGame(coordinator, log_to_db: bool=True):
    game_name = coordinator.CreateGame(log_to_db=log_to_db)
    # Creating the OpenAI environment implicitly calls JoinGame(game_name).
    environment = gym.make("CerealBar2-v0", render_mode="human", game_mode=EnvMode.LOCAL, game_name=game_name, game_coordinator=coordinator)
    leader_agent = PathfindingLeader()
    follower_agent = NaiveFollower()
    (observation, reward, done, info) = environment.reset()
    while True:
        turn_state = observation["turn_state"]
        if done:
            break
        if turn_state["role"] == Role.LEADER.value:
            # This fails here... this demo is not working yet. OpenAI GYM is a WIP. 
            leader_action = leader_agent.get_action(observation)
            logger.info(f"Leader step({leader_action})")
            (observation, reward, done, info) = environment.step(leader_action)
        else:
            follower_action = follower_agent.get_action(observation)
            logger.info(f"Follower step({follower_action})")
            (observation, reward, done, info) = environment.step(follower_action)
    # The game is over, so we can clean up the state machine.
    logger.info(f"Game over. Score: {turn_state['score']}")
    coordinator.Cleanup()
    return turn_state['score']


def main(config_filepath="server/config/local-covers-config.yaml", instruction_uuid=""):
    nest_asyncio.apply()
    # Disabling most logs improves performance by about 50ms per game.
    logging.basicConfig(level=logging.WARN)
    config = ReadConfigOrDie(config_filepath)
    db_utils.ConnectToDatabase(config)
    scores = []
    durations = []
    coordinator = LocalGameCoordinator(config)
    for i in range(10):
        logger.info(f"========================== STARTING GAME {i} ==========================")
        score = PlayGame(coordinator, instruction_uuid)
        logger.info(f"Game over. Score: {score}")
        scores.append(score)
    # Print out the scores.
    logger.warn(f"Mean score: {np.mean(scores)}")
    logger.warn(f"Mean duration: {np.mean(durations)}")

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
