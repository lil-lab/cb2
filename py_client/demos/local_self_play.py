import asyncio
import logging

from math import degrees
from time import sleep
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

class PathfindingLeader(object):
    def __init__(self):
        ...

    def get_action(self, game, map, cards, turn_state, instructions, actors, feedback):
        if has_instruction_available(instructions):
            # If the follower already has something to do, just end the turn.
            logger.info(f"Ending turn.")
            return LeadAction(LeadAction.ActionCode.END_TURN)
        if turn_state.turn == Role.FOLLOWER:
            logger.info(f"Sending nothing. Follower's turn.")
            # Don't give live feedback. Messes with the follower bot at the moment.
            return LeadAction(LeadAction.ActionCode.NONE)
        (leader, follower) = actors
        closest_card = get_next_card(cards, follower)
        if closest_card is None:
            logger.warn(f"Couldn't find a card to route to. Number of cards: {len(cards)}")
            while True:
                sleep(1)
            raise Exception("No card to select.")
        instruction = get_instruction_for_card(closest_card, follower, map, game, cards)
        logger.info(f"Lead sending: {instruction}")
        return LeadAction(LeadAction.ActionCode.SEND_INSTRUCTION, instruction=instruction)

class NaiveFollower(object):
    def __init__(self):
        self.instructions_processed = set()
        self.actions = []

    def get_action(self, game, map, cards, turn_state, instructions, actors, feedback):
        if len(self.actions) == 0:
            active_instruction = get_active_instruction(instructions)
            if active_instruction is None:
                raise Exception("No instructions to follow yet it's our turn??")
            self.actions.extend(actions_from_instruction(active_instruction.text))
            self.actions.append(FollowAction(FollowAction.ActionCode.INSTRUCTION_DONE, active_instruction.uuid))
            self.instructions_processed.add(active_instruction.uuid)
        if len(self.actions) > 0:
            action = self.actions[0]
            self.actions.pop(0)
            if action.action == FollowAction.ActionCode.INSTRUCTION_DONE:
                logger.info(f"Follow ACTION DONE.")
                sleep(3)
            return action
        else:
            # Choose a random action.
            action_codes = [FollowAction.ActionCode.FORWARDS, FollowAction.ActionCode.BACKWARDS, FollowAction.ActionCode.TURN_LEFT, FollowAction.ActionCode.TURN_RIGHT]
            action = FollowAction(random.choice(action_codes))
            return action

def main(config_filepath="server/config/local-covers-config.json"):
    logging.basicConfig(level=logging.INFO)
    config = ReadConfigOrDie(config_filepath)
    db_utils.ConnectToDatabase(config)
    coordinator = LocalGameCoordinator(config)
    game_name = coordinator.CreateGame()
    leader_game = coordinator.JoinGame(game_name)
    follower_game = coordinator.JoinGame(game_name)
    # Give the game some time to process.
    event_loop = asyncio.get_event_loop()
    event_loop.run_until_complete(asyncio.sleep(0.1))
    coordinator.StartGame(game_name)
    map, cards, turn_state, instructions, actors, live_feedback = leader_game.initial_state()
    event_loop.run_until_complete(asyncio.sleep(0.1))
    (leader, follower) = actors
    leader_agent = PathfindingLeader()
    follower_agent = NaiveFollower()
    # This is hacky, but right now step() blocks until the player can act again. This is problematic because if 
    while not leader_game.over() and not follower_game.over():
        event_loop.run_until_complete(asyncio.sleep(0.5))
        if turn_state.turn == Role.LEADER:
            leader_action = leader_agent.get_action(leader_game, map, cards, turn_state, instructions, (leader, follower), live_feedback)
            logger.info(f"leader.step()")
            map, cards, turn_state, instructions, (lleader, lfollower), live_feedback = leader_game.step(leader_action, wait_for_turn=False, check_turn=False)
            logger.info(f"leader.step() done. Turn: {turn_state.turn}")
            # If we just acted as the leader and now it's the followers turn, get masked versions of the map and cards.
            if turn_state.turn == Role.FOLLOWER:
                map, cards, turn_state, instructions, actors, live_feedback = leader_game._masked_state()
        elif turn_state.turn == Role.FOLLOWER:
            follower_action = follower_agent.get_action(follower_game, map, cards, turn_state, instructions, (None, None), live_feedback)
            logger.info(f"follower.step()")
            map, cards, turn_state, instructions, actors, live_feedback = follower_game.step(follower_action, wait_for_turn=False, check_turn=False)
            logger.info(f"follower.step() done. Turn: {turn_state.turn}")
            # If we just acted as the follower and now it's the leaders turn, get unmasked versions of the map and cards.
            if turn_state.turn == Role.LEADER:
                map, cards, turn_state, instructions, actors, live_feedback = follower_game._unmasked_state()
        else:
            raise Exception("No one's turn??")
    print(f"Game over. Score: {turn_state.score}")

if __name__ == "__main__":
    fire.Fire(main)