import logging
from datetime import timedelta
from time import sleep

import fire

from py_client.game_endpoint import Action
from py_client.remote_client import RemoteClient

logger = logging.getLogger(__name__)


def get_active_instruction(instructions):
    for instruction in instructions:
        if not instruction.completed and not instruction.cancelled:
            return instruction
    return None


REFRESH_RATE_HZ = 10


class ScenarioMonitor(object):
    def __init__(self, game_endpoint, pause_per_turn, scenario_data: str = ""):
        self.scenario_data = scenario_data
        self.instructions_processed = set()
        self.actions = []
        self.game = game_endpoint
        self.exc = None
        self.pause_per_turn = pause_per_turn

    def run(self):
        try:
            (
                map,
                cards,
                turn_state,
                instructions,
                actors,
                live_feedback,
            ) = self.game.initial_state()
            logger.info(f"Initial instructions: {instructions}")
            if self.scenario_data:
                logger.info(f"Loading scenario...")
                self.game.step(Action.LoadScenario(self.scenario_data))
            while not self.game.over():
                sleep(self.pause_per_turn)
                (
                    map,
                    cards,
                    turn_state,
                    instructions,
                    actors,
                    live_feedback,
                ) = self.game.step(Action.NoopAction())
                logger.info(f"Instructions: {instructions}")
            print(f"Game over. Score: {turn_state.score}")
        except Exception as e:
            self.exc = e

    def join(self):
        if self.exc:
            raise self.exc


def main(host, scenario_id="", render=False, lobby="scenario-lobby", scenario_file=""):
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    logging.getLogger("peewee").setLevel(logging.INFO)
    logger.info(f"Connecting to {host} (render={render}) (scenario_id={scenario_id})")
    client = RemoteClient(host, render, lobby_name=lobby)
    connected, reason = client.Connect()
    assert connected, f"Unable to connect: {reason}"

    game, reason = client.AttachToScenario(
        scenario_id=scenario_id,
        timeout=timedelta(minutes=5),
    )

    # If scenario_file is specified, read the scenario from the file.
    scenario_data = ""
    if scenario_file:
        with open(scenario_file, "r") as f:
            scenario_data = f.read()

    assert game is not None, f"Unable to join game: {reason}"
    monitor = ScenarioMonitor(
        game, pause_per_turn=(1 / REFRESH_RATE_HZ), scenario_data=scenario_data
    )
    monitor.run()
    monitor.join()


if __name__ == "__main__":
    fire.Fire(main)
