import logging
from datetime import timedelta
from time import sleep

import fire

from py_client.game_endpoint import Action, Role
from py_client.remote_client import RemoteClient

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


class NaiveFollower(object):
    def __init__(self, game_endpoint, pause_per_turn):
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
            if len(actors) == 1:
                follower = actors[0]
            else:
                (leader, follower) = actors
            if turn_state.turn != Role.FOLLOWER:
                action = Action.NoopAction()
            else:
                action = self.get_action(
                    self.game,
                    map,
                    cards,
                    turn_state,
                    instructions,
                    actors,
                    live_feedback,
                )
            logger.info(f"step({str(action)})")
            (
                map,
                cards,
                turn_state,
                instructions,
                actors,
                live_feedback,
            ) = self.game.step(action)

            while not self.game.over():
                sleep(self.pause_per_turn)
                action = self.get_action(
                    self.game,
                    map,
                    cards,
                    turn_state,
                    instructions,
                    (None, follower),
                    live_feedback,
                )
                logger.info(f"step({action})")
                (
                    map,
                    cards,
                    turn_state,
                    instructions,
                    actors,
                    live_feedback,
                ) = self.game.step(action)
            print(f"Game over. Score: {turn_state.score}")
        except Exception as e:
            self.exc = e

    def get_action(self, game, map, cards, turn_state, instructions, actors, feedback):
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
        super().join()
        if self.exc:
            raise self.exc


def main(host, render=False, e_uuid: str = "", lobby="bot-sandbox", pause_per_turn=0):
    logging.basicConfig(level=logging.INFO)
    client = RemoteClient(host, render, lobby_name=lobby)
    connected, reason = client.Connect()
    assert connected, f"Unable to connect: {reason}"
    e_uuid = e_uuid.strip()
    logger.info(f"UUID: {e_uuid}")

    game, reason = client.JoinGame(
        timeout=timedelta(minutes=5),
        queue_type=RemoteClient.QueueType.FOLLOWER_ONLY,
        e_uuid=e_uuid.strip(),
    )
    assert game is not None, f"Unable to join game: {reason}"
    follower = NaiveFollower(game, pause_per_turn)
    follower.run()


if __name__ == "__main__":
    fire.Fire(main)
