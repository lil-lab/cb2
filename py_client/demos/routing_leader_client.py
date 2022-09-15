import logging

from math import degrees
from time import sleep
from py_client.remote_client import RemoteClient
from py_client.game_endpoint import LeadAction, FollowAction, LeadFeedbackAction, Role

import fire

from collections import deque

from datetime import timedelta

from random import choice

logger = logging.getLogger(__name__)

def card_collides(cards, new_card):
    card_colors = [card.card_init.color for card in cards]
    card_shapes = [card.card_init.shape for card in cards]
    card_counts = [card.card_init.count for card in cards]
    return (new_card.card_init.color in card_colors or new_card.card_init.shape
        in card_shapes or new_card.card_init.count in card_counts)
    
def get_next_card(cards, follower):
    distance_to_follower = lambda c: c.prop_info.location.distance_to(follower.location())
    selected_cards = []
    for card in cards:
        if card.card_init.selected:
            selected_cards.append(card)
    closest_card = None
    for card in cards:
        if not card_collides(selected_cards, card):
            if closest_card is None or distance_to_follower(card) < distance_to_follower(closest_card):
                closest_card = card
    return closest_card

def find_path_to_card(card, follower, map, cards):
    start_location = follower.location()
    end_location = card.prop_info.location
    card_locations = set([card.prop_info.location for card in cards])
    location_queue = deque()
    location_queue.append((start_location, [start_location]))
    visited_locations = set()
    while len(location_queue) > 0:
        current_location, current_path = location_queue.popleft()
        if current_location in visited_locations:
            continue
        visited_locations.add(current_location)
        if current_location == end_location:
            return current_path
        tile = map.tile_at(current_location)
        for neighbor in tile.cell.coord.neighbors():
            if tile.cell.boundary.get_edge_between(tile.cell.coord, neighbor):
                break
            if neighbor in card_locations and neighbor != end_location:
                break
            location_queue.append((neighbor, current_path + [neighbor]))
    return None

def get_instruction_for_card(card, follower, map, game_endpoint, cards):
    distance_to_follower = lambda c: c.prop_info.location.distance_to(follower.location())
    path = find_path_to_card(card, follower, map, cards)
    if not path:
        return "No path found. :("
    game_endpoint.visualization().set_trajectory([(coord, 0) for coord in path])
    heading = follower.heading_degrees() - 60
    instructions = []
    for idx, location in enumerate(path):
        next_location = path[idx + 1] if idx + 1 < len(path) else None
        if not next_location:
            break
        degrees_away = location.degrees_to(next_location) - heading
        if degrees_away < 0:
            degrees_away += 360
        if degrees_away > 180:
            degrees_away -= 360
        # Pre-defined shortcuts to introduce backstepping.
        if degrees_away == 180:
            instructions.append("backward")
            location = next_location
            continue
        if degrees_away == 120:
            instructions.append("left")
            instructions.append("backward")
            heading -= 60
            location = next_location
            continue
        if degrees_away == -120:
            instructions.append("right")
            instructions.append("backward")
            heading += 60
            location = next_location
            continue
        # General-case movement pattern.
        if degrees_away > 0:
            instructions.extend(["right"] * int(degrees_away / 60))
        else:
            instructions.extend(["left"] * int(-degrees_away / 60))
        heading += degrees_away
        instructions.append("forward")
        location = next_location

    return ', '.join(instructions)

def get_distance_to_card(card, follower):
    distance_to_follower = lambda c: c.prop_info.location.distance_to(follower.location())
    return distance_to_follower(card)

def has_instruction_available(instructions):
    for instruction in instructions:
        if not instruction.completed and not instruction.cancelled:
            return True
    return False

def main(host, render=False):
    logging.basicConfig(level=logging.INFO)
    client = RemoteClient(host, render)
    connected, reason = client.Connect()
    assert connected, f"Unable to connect: {reason}"
    with client.JoinGame(timeout=timedelta(minutes=5), queue_type=RemoteClient.QueueType.LEADER_ONLY) as game:
        map, cards, turn_state, instructions, (leader, follower), live_feedback = game.initial_state()
        closest_card = get_next_card(cards, follower)
        action = LeadAction(LeadAction.ActionCode.SEND_INSTRUCTION, instruction=get_instruction_for_card(closest_card, follower, map, game, cards))
        follower_distance_to_card = float("inf")
        while not game.over():
            print(f"step()")
            if type(action) == LeadAction and action.action == LeadAction.ActionCode.END_TURN:
                sleep(0.2)
            map, cards, turn_state, instructions, (leader, follower), live_feedback = game.step(action)
            closest_card = get_next_card(cards, follower)
            if turn_state.turn == Role.LEADER:
                if has_instruction_available(instructions):
                    action = LeadAction(LeadAction.ActionCode.END_TURN)
                else:
                    action = LeadAction(LeadAction.ActionCode.SEND_INSTRUCTION, instruction=get_instruction_for_card(closest_card, follower, map, game, cards))
            if turn_state.turn == Role.FOLLOWER:
                # Don't give live feedback. Messes with the follower bot at the moment.
                action = LeadFeedbackAction(LeadFeedbackAction.ActionCode.NONE)
                continue
    print(f"Game over. Score: {turn_state.score}")

if __name__ == "__main__":
    fire.Fire(main)