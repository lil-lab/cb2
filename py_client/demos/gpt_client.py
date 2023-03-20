import logging
from datetime import timedelta

import fire
import openai

from py_client.client_utils import DescribeMap, FollowerSystemPrompt
from py_client.game_endpoint import Action
from py_client.remote_client import RemoteClient
from server.messages.prop import PropUpdate

logger = logging.getLogger(__name__)

# Replace "your_openai_key_here" with your actual OpenAI API key
openai.api_key = "your_openai_key_here"


def actions_from_code(action_code, i_uuid: str = None):
    # Split action code by comma.
    characters_in_prompt = action_code.split(",")
    if len(characters_in_prompt) == 0:
        logger.warning("Empty action string.")
        return None
    actions = []
    for c in characters_in_prompt:
        # Convert to lower.
        c = c.lower()
        logger.info(f"Action code: `{c}`")
        if "forward".startswith(c):
            actions.append(Action.Forwards())
        elif "backward".startswith(c):
            actions.append(Action.Backwards())
        elif "left".startswith(c):
            actions.append(Action.Left())
        elif "right".startswith(c):
            actions.append(Action.Right())
        elif "done".startswith(c):
            actions.append(Action.InstructionDone(i_uuid))
        else:
            logger.warning(f"Invalid action code: {c}")
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


class GPTFollower(object):
    def __init__(self, game_endpoint, pause_per_turn):
        self.instructions_processed = set()
        self.actions = []
        self.game = game_endpoint
        self.exc = None
        self.pause_per_turn = pause_per_turn

    def run(self):
        # Start with the system prompt, explaining the rules of the game.
        game_history = [
            {
                "role": "system",
                "content": FollowerSystemPrompt(),
            },
        ]
        try:
            game_state = self.game.initial_state()
            (_, _, turn_state, _, _, _) = game_state
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

                if len(self.actions) == 0:
                    game_history.append(
                        {
                            "role": "user",
                            "content": description + "\n Enter action: ",
                        }
                    )

                    response = openai.ChatCompletion.create(
                        model="gpt-4",
                        messages=game_history,
                        max_tokens=10,
                        n=1,
                        stop=["\n"],
                        temperature=0.5,
                    )

                    action_code = response.choices[0].message.content.strip()
                    print(f"GPT-4 action: `{action_code}`")

                    game_history.append(
                        {
                            "role": "assistant",
                            "content": action_code,
                        }
                    )

                    active_instruction = get_active_instruction(instrs)
                    actions = actions_from_code(action_code, active_instruction.uuid)
                    if len(actions) == 0:
                        # Instead of rapidly polling OpenAI, just quit.
                        logger.info("No actions. Quitting.")
                        break
                    self.actions.extend(actions)
                action = self.actions.pop(0)
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
    client = RemoteClient(host, render, lobby_name=lobby)
    connected, reason = client.Connect()
    assert connected, f"Unable to connect: {reason}"

    game, reason = client.JoinGame(
        timeout=timedelta(minutes=5),
        queue_type=RemoteClient.QueueType.FOLLOWER_ONLY,
    )
    assert game is not None, f"Unable to join game: {reason}"

    # Handles game logic.
    follower = GPTFollower(game, pause_per_turn)
    follower.run()
    follower.join()


if __name__ == "__main__":
    fire.Fire(main)
