from py_client.cb2_client import Game, Cb2Client, LeadAction, FollowAction, LeadFeedbackAction

import fire

from datetime import timedelta

from joke.jokes import *

from random import choice

def RandomJoke():
    return choice([geek, icanhazdad, chucknorris, icndb])()

def main(host):
    client = Cb2Client(host)
    connected, reason = client.Connect()
    assert connected, f"Unable to connect: {reason}"
    with client.JoinGame(timeout=timedelta(minutes=5), queue_type=Cb2Client.QueueType.LEADER_ONLY) as game:
        if game.player_role() != Cb2Client.Role.LEADER:
            raise Exception("Not a leader! I quit!")
        map, cards, state, instructions, actors = game.state()
        action = LeadAction(LeadAction.ActionCode.SEND_INSTRUCTION, instruction=RandomJoke())
        every_other_action = False
        while not game.over():
            map, cards, state, instructions, actors = game.step(action)
            if state.role == Cb2Client.Role.FOLLOWER:
                action = LeadFeedbackAction(choice([LeadFeedbackAction.ActionCode.POSITIVE_FEEDBACK, LeadFeedbackAction.ActionCode.NEGATIVE_FEEDBACK]))
                continue
            action = LeadAction(LeadAction.ActionCode.SEND_INSTRUCTION, instruction=RandomJoke())
            if every_other_action:
                action = LeadAction(LeadAction.ActionCode.END_TURN)
            every_other_action = not every_other_action
    print(f"Game over. Score: {state.score}")
    
if __name__ == "__main__":
    fire.Fire(main)