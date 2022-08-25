from math import degrees
from time import sleep
from py_client.cb2_client import Game, Cb2Client, LeadAction, FollowAction, LeadFeedbackAction, Role

import fire
import logging

from datetime import timedelta
from random import choice

logger = logging.getLogger(__name__)

def actions_from_instruction(instruction):
    actions = []
    instruction_action_codes = instruction.split(",")
    for action_code in instruction_action_codes:
        action_code = action_code.strip()
        if action_code == "forward":
            actions.append(FollowAction(FollowAction.ActionCode.FORWARDS))
        elif action_code == "backward":
            actions.append(FollowAction(FollowAction.ActionCode.BACKWARDS))
        elif action_code == "left":
            actions.append(FollowAction(FollowAction.ActionCode.TURN_LEFT))
        elif action_code == "right":
            actions.append(FollowAction(FollowAction.ActionCode.TURN_RIGHT))
    return actions

def get_active_instruction(instructions):
    for instruction in instructions:
        logger.info(f"INSTRUCTION: {instruction}")
        if not instruction.completed and not instruction.cancelled:
            logger.info(f"FOUND ACTIVE INSTRUCTION: {instruction.text}")
            return instruction
    return None

def main(host):
    client = Cb2Client(host)
    connected, reason = client.Connect()
    assert connected, f"Unable to connect: {reason}"
    actions = []
    instruction_in_progress = False
    active_uuid = None
    with client.JoinGame(timeout=timedelta(minutes=5), queue_type=Cb2Client.QueueType.FOLLOWER_ONLY) as game:
        map, cards, turn_state, instructions, (leader, follower), feedback = game.initial_state()
        action = FollowAction(FollowAction.ActionCode.NONE)
        while not game.over():
            print(f"step({action.action})")
            sleep(1)
            map, cards, turn_state, instructions, (leader, follower), feedback = game.step(action)
            if feedback != None:
                print(f"FEEDBACK: {feedback}")
            if turn_state.turn != Role.FOLLOWER:
                raise Exception("Not follower's turn yet step() returned. Weird!")
            if len(actions) == 0:
                active_instruction = get_active_instruction(instructions)
                if active_instruction is None:
                    raise Exception("No instructions to follow yet it's our turn??")
                else:
                    actions.extend(actions_from_instruction(active_instruction.text))
                    actions.append(FollowAction(FollowAction.ActionCode.INSTRUCTION_DONE, active_instruction.uuid))
            if len(actions) > 0:
                action = actions[0]
                actions.pop(0)
    print(f"Game over. Score: {turn_state.score}")

if __name__ == "__main__":
    fire.Fire(main)