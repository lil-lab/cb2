import logging
from datetime import timedelta

import fire

from py_client.client_utils import DescribeMap, FollowerSystemPrompt
from py_client.game_endpoint import Action
from py_client.remote_client import RemoteClient
from server.messages.prop import PropUpdate

logger = logging.getLogger(__name__)


def actions_from_code(action_code, i_uuid: str = None):
    if len(action_code) == 0:
        return None
    # Convert to lower.
    action_code = action_code.lower()
    if "forward".startswith(action_code):
        return Action.Forwards()
    elif "backward".startswith(action_code):
        return Action.Backwards()
    elif "left".startswith(action_code):
        return Action.Left()
    elif "right".startswith(action_code):
        return Action.Right()
    elif "done".startswith(action_code):
        return Action.InstructionDone(i_uuid)
    return None


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


class CliFollower(object):
    def __init__(self, game_endpoint, pause_per_turn):
        self.instructions_processed = set()
        self.actions = []
        self.game = game_endpoint
        self.exc = None
        self.pause_per_turn = pause_per_turn

    def run(self):
        try:
            logger.info(FollowerSystemPrompt())
            game_state = self.game.initial_state()
            (_, _, turn_state, _, _, _) = game_state
            # It's always the leader's turn first. Wait for follower turn by executing a noop.
            action = Action.NoopAction()
            game_state = self.game.step(action)
            while not self.game.over():
                (mapu, props, turn_state, instrs, actors, feedback) = game_state
                prop_update = PropUpdate(props)
                (leader, follower) = get_actors(game_state)
                description = DescribeMap(
                    mapu, prop_update, instrs, turn_state, follower, leader
                )
                print("===============================")
                print(description)
                # Prompt for input.
                action_code = input("Enter action: ")
                active_instruction = get_active_instruction(instrs)
                action = actions_from_code(action_code, active_instruction.uuid)
                if action is None:
                    print("Invalid action. NOPing.")
                    action = Action.NoopAction()
                logger.info(f"step({action})")
                game_state = self.game.step(action)
                (_, _, turn_state, _, _, _) = game_state
            print(f"Game over. Score: {turn_state.score}")
        except Exception as e:
            self.exc = e

    def join(self):
        if self.exc:
            raise self.exc


def main(host, render=False, lobby="bot-sandbox", pause_per_turn=0):
    # Create client and connect to server.
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
    follower = CliFollower(game, pause_per_turn)
    follower.run()
    follower.join()


if __name__ == "__main__":
    fire.Fire(main)
