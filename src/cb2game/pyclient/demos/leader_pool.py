import asyncio
import logging
import time

import fire
import nest_asyncio

from cb2game.pyclient.demos.routing_leader_client import *
from cb2game.pyclient.remote_client import *

logger = logging.getLogger(__name__)


class PathfindingLeader(threading.Thread):
    def __init__(self, url, index):
        super().__init__()
        self.url = url
        self.exc = None
        self.index = index

    def get_action(self, game, map, cards, turn_state, instructions, actors, feedback):
        if turn_state.turn != Role.LEADER:
            return Action.NoopAction()
        if has_instruction_available(instructions):
            # If the follower already has something to do, just end the turn.
            return Action.EndTurn()
        (leader, follower) = actors
        closest_card = get_next_card(cards, follower)
        if closest_card is None:
            logger.warning(
                f"Need to debug this. Couldn't find a card to route to. Number of cards: {len(cards)}"
            )
            return Action.SendInstruction("Error: no cards found :/")
        instruction = get_instruction_for_card(closest_card, follower, map, game, cards)
        return Action.SendInstruction(instruction=instruction)

    def run(self):
        try:
            pass

            event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(event_loop)
            client = RemoteClient(self.url, render=False)
            joined, reason = client.Connect()
            assert joined, f"Unable to join: {reason}"
            self.game, reason = client.JoinGame(
                queue_type=RemoteClient.QueueType.LEADER_ONLY
            )
            assert self.game is not None, f"Unable to join game: {reason}"
            (
                map,
                cards,
                turn_state,
                instructions,
                (leader, follower),
                live_feedback,
            ) = self.game.initial_state()
            while not self.game.over():
                leader_action = self.get_action(
                    self.game,
                    map,
                    cards,
                    turn_state,
                    instructions,
                    (leader, follower),
                    live_feedback,
                )
                logger.info(f"Leader {self.index} step({str(leader_action)})")
                (
                    map,
                    cards,
                    turn_state,
                    instructions,
                    (leader, follower),
                    live_feedback,
                ) = self.game.step(leader_action)
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


def main(url="http://localhost:8080", number_of_leaders=32):
    """This utility maintains a pool of leaders who play games. It is intended to be used for evaluation of games."""
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
        time.sleep(1)


if __name__ == "__main__":
    fire.Fire(main)
