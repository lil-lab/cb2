from py_client.demos.routing_leader_client import *
from py_client.remote_client import *
from server.config.config import ReadConfigOrDie

import asyncio
import fire
import logging
import nest_asyncio
import queue

logger = logging.getLogger(__name__)

class PathfindingLeader(threading.Thread):
    def __init__(self, url, index):
        super().__init__()
        self.url = url
        self.exc = None
        self.index = index

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
        return LeadAction(LeadAction.ActionCode.SEND_INSTRUCTION, instruction=instruction)
    
    def run(self):
        try:
            import time
            event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(event_loop)
            client = RemoteClient(self.url, render=False)
            joined, reason = client.Connect()
            assert joined, f"Unable to join: {reason}"
            self.game = client.JoinGame(queue_type=RemoteClient.QueueType.LEADER_ONLY)
            map, cards, turn_state, instructions, (leader, follower), live_feedback = self.game.initial_state()
            while not self.game.over():
                leader_action = self.get_action(self.game, map, cards, turn_state, instructions, (leader, follower), live_feedback)
                logger.info(f"Leader {self.index} step({str(leader_action)})")
                map, cards, turn_state, instructions, (leader, follower), live_feedback = self.game.step(leader_action)
            self.game.close()
        except Exception as e:
            self.exc = e
        
    def join(self):
        super().join()
        if self.exc:
            raise self.exc
    
    def assert_ok(self):
        if self.exc:
            raise self.exc

def main(url="http://localhost:8080", number_of_leaders = 32):
    """ This utility maintains a pool of leaders who play games. It is intended to be used for evaluation of games."""
    nest_asyncio.apply()
    logging.basicConfig(level=logging.INFO)
    logger.info(f"number_of_leaders: {number_of_leaders}")
    leaders = []
    for i in range(number_of_leaders):
        leader_agent = PathfindingLeader(url, i)
        leader_agent.daemon = True
        leader_agent.start()
        leaders.append(leader_agent)
    
    while True:
        for i in range(number_of_leaders):
            if not leaders[i].is_alive():
                logger.info(f"Leader {i} died. Restarting.")
                leaders[i].assert_ok()
                leader_agent = PathfindingLeader(url, i)
                leader_agent.daemon = True
                leader_agent.start()
                leaders[i] = leader_agent

if __name__ == "__main__":
    fire.Fire(main)