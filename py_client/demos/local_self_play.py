import asyncio
import logging
import matplotlib
import matplotlib.pyplot as plt
import nest_asyncio
import numpy as np
import pygame
import threading

from math import degrees
from py_client.remote_client import RemoteClient
from py_client.game_endpoint import LeadAction, FollowAction, LeadFeedbackAction, Role
from py_client.demos.follower_client import *
from py_client.demos.routing_leader_client import *
from py_client.local_game_coordinator import LocalGameCoordinator

from server.config.config import ReadConfigOrDie
import server.db_tools.db_utils as db_utils

import fire

from collections import deque
from datetime import timedelta
from random import choice

logger = logging.getLogger(__name__)

class PathfindingLeader(threading.Thread):
    def __init__(self, game_endpoint):
        super().__init__()
        self.game = game_endpoint
        self.exc = None

    def get_action(self, game, map, cards, turn_state, instructions, actors, feedback):
        if turn_state.turn != Role.LEADER:
            return LeadFeedbackAction(LeadFeedbackAction.ActionCode.NONE)
        if has_instruction_available(instructions):
            # If the follower already has something to do, just end the turn.
            return LeadAction(LeadAction.ActionCode.END_TURN)
        (leader, follower) = actors
        closest_card = get_next_card(cards, follower)
        if closest_card is None:
            logger.warn(f"Need to debug this. Couldn't find a card to route to. Number of cards: {len(cards)}")
            return LeadAction(LeadAction.ActionCode.SEND_INSTRUCTION, "Error: no cards found :/")
        instruction = get_instruction_for_card(closest_card, follower, map, game, cards)
        logger.info(f"Lead sending: {instruction}")
        return LeadAction(LeadAction.ActionCode.SEND_INSTRUCTION, instruction=instruction)
    
    def run(self):
        try:
            logger.info(f"LEAD STARTED()")
            initialized, reason = self.game.Initialize()
            assert initialized, f"Unable to initialize: {reason}"
            map, cards, turn_state, instructions, (leader, follower), live_feedback = self.game.initial_state()
            if turn_state.turn == Role.LEADER:
                action = self.get_action(self.game, map, cards, turn_state, instructions, (leader, follower), live_feedback)
            else:
                action = LeadAction(LeadAction.ActionCode.NONE)
            while not self.game.over():
                leader_action = self.get_action(self.game, map, cards, turn_state, instructions, (leader, follower), live_feedback)
                logger.info(f"LEAD STEP({str(leader_action)})")
                map, cards, turn_state, instructions, (leader, follower), live_feedback = self.game.step(leader_action)
                logger.info(f"LEAD STEP DONE()")
        except Exception as e:
            self.exc = e
        
    def join(self):
        super().join()
        if self.exc:
            raise self.exc

class NaiveFollower(threading.Thread):
    def __init__(self, game_endpoint):
        super().__init__()
        self.instructions_processed = set()
        self.actions = []
        self.game = game_endpoint
        self.exc = None
    
    def run(self):
        try:
            initialized, reason = self.game.Initialize()
            assert initialized, f"Unable to initialize: {reason}"
            map, cards, turn_state, instructions, actors, live_feedback = self.game.initial_state()
            if len(actors) == 1:
                follower = actors[0]
            else:
                (leader, follower) = actors
            if turn_state.turn == Role.FOLLOWER:
                action = self.get_action(self.game, map, cards, turn_state, instructions, actors, live_feedback)
            else:
                action = FollowAction(FollowAction.ActionCode.NONE)
            map, cards, turn_state, instructions, actors, live_feedback = self.game.step(action)
            while not self.game.over():
                action = self.get_action(self.game, map, cards, turn_state, instructions, (None, follower), live_feedback)
                map, cards, turn_state, instructions, actors, live_feedback = self.game.step(action)
        except Exception as e:
            self.exc = e

    def get_action(self, game, map, cards, turn_state, instructions, actors, feedback):
        if len(self.actions) == 0:
            active_instruction = get_active_instruction(instructions)
            actions = []
            if active_instruction is not None:
                actions = actions_from_instruction(active_instruction.text)
            else:
                logger.info(f"Need to debug this.")
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

    def join(self):
        super().join()
        if self.exc:
            raise self.exc

def main(config_filepath="server/config/local-covers-config.json", instruction_uuid=""):
    nest_asyncio.apply()
    logging.basicConfig(level=logging.INFO)
    config = ReadConfigOrDie(config_filepath)
    db_utils.ConnectToDatabase(config)
    scores = []
    durations = []
    for i in range(10):
        logger.info(f"========================== STARTING GAME {i} ==========================")
        coordinator = LocalGameCoordinator(config)
        if len(instruction_uuid) > 0:
            game_name = coordinator.CreateGameFromDatabase(instruction_uuid)
        else:
            game_name = coordinator.CreateGame()
        leader_game = coordinator.JoinGame(game_name)
        follower_game = coordinator.JoinGame(game_name)
        # Give the game some time to process.
        coordinator.StartGame(game_name)
        leader_agent = PathfindingLeader(leader_game)
        follower_agent = NaiveFollower(follower_game)
        leader_agent.daemon = True
        follower_agent.daemon = True
        leader_agent.start()
        follower_agent.start()
        event_loop = asyncio.get_event_loop()
        event_loop.run_until_complete(asyncio.sleep(1))
        while not coordinator._state_machine_driver(game_name).done():
            event_loop.run_until_complete(asyncio.sleep(1))
            viz = leader_game.visualization()
            viz.draw()
            pygame.display.flip()
        leader_agent.join()
        follower_agent.join()
        print(f"Game over. Score: {leader_game.score()}, Duration: {leader_game.game_duration().total_seconds()}")
        scores.append(leader_game.score())
        durations.append(leader_game.game_duration().total_seconds())
    # Print out the scores.
    print(f"Mean score: {np.mean(scores)}")
    print(f"Mean duration: {np.mean(durations)}")

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