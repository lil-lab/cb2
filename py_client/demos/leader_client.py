from datetime import timedelta
from time import sleep

import fire

from py_client.game_endpoint import Action, Role
from py_client.remote_client import RemoteClient


def card_collides(cards, new_card):
    card_colors = [card.card_init.color for card in cards]
    card_shapes = [card.card_init.shape for card in cards]
    card_counts = [card.card_init.count for card in cards]
    return (
        new_card.card_init.color in card_colors
        or new_card.card_init.shape in card_shapes
        or new_card.card_init.count in card_counts
    )


def get_next_card(cards, follower):
    distance_to_follower = lambda c: c.prop_info.location.distance_to(
        follower.location()
    )
    selected_cards = []
    for card in cards:
        if card.card_init.selected:
            selected_cards.append(card)
    closest_card = None
    for card in cards:
        if not card_collides(selected_cards, card):
            if closest_card is None or distance_to_follower(
                card
            ) < distance_to_follower(closest_card):
                closest_card = card
    return closest_card


def get_instruction_for_card(card, follower):
    distance_to_follower = lambda c: c.prop_info.location.distance_to(
        follower.location()
    )
    degrees_away = (
        follower.location().degrees_to(card.prop_info.location)
        + 60
        - follower.heading_degrees()
    )
    if degrees_away < 0:
        degrees_away += 360
    if degrees_away > 180:
        degrees_away -= 360
    distance_away = distance_to_follower(card)
    return f"There is a card at {degrees_away} degrees from you and {distance_away} units away."


def get_distance_to_card(card, follower):
    distance_to_follower = lambda c: c.prop_info.location.distance_to(
        follower.location()
    )
    return distance_to_follower(card)


def has_instruction_available(instructions):
    for instruction in instructions:
        if not instruction.completed and not instruction.cancelled:
            return True
    return False


def main(host, render=False):
    client = RemoteClient(host, render)
    connected, reason = client.Connect()
    assert connected, f"Unable to connect: {reason}"
    game, reason = client.JoinGame(
        timeout=timedelta(minutes=5), queue_type=RemoteClient.QueueType.LEADER_ONLY
    )
    assert game is not None, f"Unable to join game: {reason}"
    (
        map,
        cards,
        turn_state,
        instructions,
        (leader, follower),
        live_feedback,
    ) = game.initial_state()
    closest_card = get_next_card(cards, follower)
    action = Action.SendInstruction(get_instruction_for_card(closest_card, follower))
    follower_distance_to_card = float("inf")
    while not game.over():
        print(f"step()")
        if action.is_end_turn():
            sleep(2)
        (
            map,
            cards,
            turn_state,
            instructions,
            (leader, follower),
            live_feedback,
        ) = game.step(action)
        closest_card = get_next_card(cards, follower)
        if turn_state.turn == Role.LEADER:
            if has_instruction_available(instructions):
                action = Action.EndTurn()
            else:
                action = Action.SendInstruction(
                    get_instruction_for_card(closest_card, follower)
                )
        if turn_state.turn == Role.FOLLOWER:
            if closest_card != None:
                distance_to_card = get_distance_to_card(closest_card, follower)
                if distance_to_card < follower_distance_to_card:
                    action = Action.PositiveFeedback()
                elif distance_to_card > follower_distance_to_card:
                    action = Action.NegativeFeedback()
                else:
                    action = Action.NoopAction()
            else:
                action = Action.NoopAction()
    print(f"Game over. Score: {turn_state.score}")


if __name__ == "__main__":
    fire.Fire(main)
