import logging
from datetime import timedelta
from time import sleep

import fire

from cb2game.pyclient.game_endpoint import Action
from cb2game.pyclient.remote_client import RemoteClient

logger = logging.getLogger(__name__)


def actions_from_instruction(instruction):
    actions = []
    instruction_action_codes = instruction.split(",")
    for action_code in instruction_action_codes:
        action_code = action_code.strip().lower()
        if len(action_code) == 0:
            continue
        if "forward".startswith(action_code):
            actions.append(Action.Forwards())
        elif "backward".startswith(action_code):
            actions.append(Action.Backwards())
        elif "left".startswith(action_code):
            actions.append(Action.Left())
        elif "right".startswith(action_code):
            actions.append(Action.Right())
        elif "random".startswith(action_code):
            actions.append(Action.RandomMovementAction())
    if len(actions) == 0:
        # Choose a random action.
        Action.RandomMovementAction()
    return actions


def get_active_instruction(instructions):
    for instruction in instructions:
        if not instruction.completed and not instruction.cancelled:
            return instruction
    return None


def get_actors(game_state):
    (
        _,
        _,
        _,
        _,
        actors,
        _,
    ) = game_state
    if len(actors) == 1:
        return (None, actors[0])
    else:
        return actors


class NaiveFollower(object):
    def __init__(self, game_endpoint, pause_per_turn):
        self.instructions_processed = set()
        self.actions = []
        self.game = game_endpoint
        self.exc = None
        self.pause_per_turn = pause_per_turn

    def run(self):
        try:
            game_state = self.game.initial_state()
            (_, _, turn_state, _, _, _) = game_state
            # It's always the leader's turn first. Wait for follower turn by executing a noop.
            action = Action.NoopAction()
            game_state = self.game.step(action)
            while not self.game.over():
                action = self.get_action(game_state)
                logger.info(f"step({action})")
                game_state = self.game.step(action)
                if self.game.timeout_occurred():
                    logger.warning("/// Timeout occurred ///")
                sleep(self.pause_per_turn)
                (_, _, turn_state, _, _, _) = game_state
            print(f"Game over. Score: {turn_state.score}")
        except Exception as e:
            self.exc = e

    def get_action(self, game_state):
        (map, cards, turn_state, instructions, actors, feedback) = game_state
        if len(self.actions) == 0:
            active_instruction = get_active_instruction(instructions)
            actions = []
            if active_instruction is not None:
                actions = actions_from_instruction(active_instruction.text)
            else:
                logger.info(f"Num of instructions: {len(instructions)}")
                for instruction in instructions:
                    logger.info(f"INSTRUCTION: {instruction}")
                logger.info(f"step() returned but no active instruction.")
            self.actions.extend(actions)
            if active_instruction is not None:
                self.actions.append(Action.InstructionDone(active_instruction.uuid))
                self.instructions_processed.add(active_instruction.uuid)
        if len(self.actions) > 0:
            action = self.actions[0]
            self.actions.pop(0)
            return action
        else:
            # Choose a random action.
            return Action.RandomMovementAction()

    def join(self):
        if self.exc:
            raise self.exc


def main(host, render=False, lobby="bot-sandbox", pause_per_turn=0):
    # Create client and connect to server.
    logging.basicConfig(level=logging.INFO)
    client = RemoteClient(host, render, lobby_name=lobby)
    connected, reason = client.Connect()
    assert connected, f"Unable to connect: {reason}"

    # Wait in the queue for a game to start.
    game, reason = client.JoinGame(
        timeout=timedelta(minutes=5),
        queue_type=RemoteClient.QueueType.FOLLOWER_ONLY,
    )
    assert game is not None, f"Unable to join game: {reason}"

    # Handles game logic.
    follower = NaiveFollower(game, pause_per_turn)
    follower.run()
    follower.join()


if __name__ == "__main__":
    fire.Fire(main)
