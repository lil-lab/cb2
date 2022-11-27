# Re-creation of py_client/demos/local_self_play.py using the OpenAI gym.
import logging
import threading
import time
from collections import deque

import fire
import gym
import matplotlib.pyplot as plt
import nest_asyncio
import numpy as np

import server.db_tools.db_utils as db_utils
from envs.cb2 import EnvMode
from py_client.game_endpoint import Action, Role
from py_client.local_game_coordinator import LocalGameCoordinator
from server.config.config import ReadConfigOrDie
from server.hex import HecsCoord
from server.messages.map_update import MapUpdate
from server.messages.prop import PropUpdate

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


def card_collides(cards, new_card):
    card_colors = [card.card_init.color for card in cards]
    card_shapes = [card.card_init.shape for card in cards]
    card_counts = [card.card_init.count for card in cards]
    return (
        new_card.card_init.color in card_colors
        or new_card.card_init.shape in card_shapes
        or new_card.card_init.count in card_counts
    )


def get_active_instruction(instructions):
    for instruction in instructions:
        if not instruction.completed and not instruction.cancelled:
            return instruction
    return None


def has_instruction_available(instructions):
    for instruction in instructions:
        if not instruction.completed and not instruction.cancelled:
            return True
    return False


def get_next_card(observation):
    (_, follower) = observation["actors"]["leader"], observation["actors"]["follower"]
    distance_to_follower = lambda c: c.prop_info.location.distance_to(
        HecsCoord.from_offset(follower["location"][0], follower["location"][1])
    )
    selected_cards = []
    prop_update = PropUpdate.from_gym_state(observation)
    cards = prop_update.props
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


def find_path_to_card(card, follower, map, cards):
    start_location = HecsCoord.from_offset(
        follower["location"][0], follower["location"][1]
    )
    end_location = card.prop_info.location
    location_queue = deque()
    location_queue.append((start_location, [start_location]))
    card_locations = set([card.prop_info.location for card in cards])
    if start_location in card_locations:
        card_locations.remove(start_location)
    if end_location in card_locations:
        card_locations.remove(end_location)
    visited_locations = set()
    while len(location_queue) > 0:
        current_location, current_path = location_queue.popleft()
        if current_location in visited_locations:
            continue
        if current_location in card_locations:
            continue
        visited_locations.add(current_location)
        if current_location == end_location:
            return current_path
        tile = map.tile_at(current_location)
        for neighbor in tile.cell.coord.neighbors():
            if tile.cell.boundary.get_edge_between(tile.cell.coord, neighbor):
                continue
            neighbor_tile = map.tile_at(neighbor)
            if neighbor_tile.cell.boundary.get_edge_between(neighbor, tile.cell.coord):
                continue
            location_queue.append((neighbor, current_path + [neighbor]))
    return None


def get_instruction_for_card(card, observation, game_endpoint=None):
    prop_update = PropUpdate.from_gym_state(observation)
    cards = prop_update.props
    (_, follower) = observation["actors"]["leader"], observation["actors"]["follower"]

    distance_to_follower = lambda c: c.prop_info.location.distance_to(
        follower.location()
    )
    map_update = MapUpdate.from_gym_state(observation)
    path = find_path_to_card(card, follower, map_update, cards)
    if not path:
        return "random, random, random, random, random"
    game_vis = game_endpoint.visualization() if game_endpoint else None
    if game_vis is not None:
        game_vis.set_trajectory([(coord, 0) for coord in path])
    heading = follower["rotation"] - 60
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

    return ", ".join(instructions)


class PathfindingLeader(threading.Thread):
    def __init__(self):
        super().__init__()
        self.exc = None

    def get_action(self, observation):
        turn_state = observation["turn_state"]
        if turn_state["role"] != Role.LEADER:
            return Action.NoopAction()
        if has_instruction_available(observation["instructions"]):
            # If the follower already has something to do, just end the turn.
            return Action.EndTurn()
        (leader, follower) = (
            observation["actors"]["leader"],
            observation["actors"]["follower"],
        )
        observation["cards"]
        closest_card = get_next_card(observation)
        if closest_card is None:
            # Just have the follower make random moves, hope something happens...
            return Action.SendInstruction(
                "random, random, random, random, random, random"
            )
        instruction = get_instruction_for_card(closest_card, observation)
        logger.info(f"Lead sending: {instruction}")
        return Action.SendInstruction(instruction)


class NaiveFollower(threading.Thread):
    def __init__(self):
        super().__init__()
        self.instructions_processed = set()
        self.actions = []
        self.exc = None

    def get_action(self, observation):
        instructions = observation["instructions"]
        if len(self.actions) == 0:
            active_instruction = get_active_instruction(instructions)
            actions = []
            if active_instruction is not None:
                actions = actions_from_instruction(active_instruction.text)
            else:
                raise Exception(f"No active instruction. Instructions: {instructions}")
            if len(actions) == 0:
                actions = [Action.RandomMovementAction() for _ in range(5)]
            self.actions.extend(actions)
            if active_instruction is not None:
                self.actions.append(Action.InstructionDone(active_instruction.uuid))
                self.instructions_processed.add(active_instruction.uuid)
                self.instructions_processed.add(active_instruction.uuid)
        if len(self.actions) > 0:
            action = self.actions[0]
            self.actions.pop(0)
            return action
        else:
            # Choose a random action.
            return Action.RandomMovementAction()


def PlayGame(coordinator, log_to_db: bool = True):
    game_name = coordinator.CreateGame(log_to_db=log_to_db)
    # Creating the OpenAI environment implicitly calls JoinGame(game_name).
    environment = gym.make(
        "CerealBar2-v0",
        render_mode="human",
        game_mode=EnvMode.LOCAL,
        game_name=game_name,
        game_coordinator=coordinator,
    )
    leader_agent = PathfindingLeader()
    follower_agent = NaiveFollower()
    start = time.time()
    (observation, reward, done, truncated, info) = environment.reset()
    while True:
        turn_state = observation["turn_state"]
        if done:
            break
        if turn_state["role"] == Role.LEADER:
            # This fails here... this demo is not working yet. OpenAI GYM is a WIP.
            leader_action = leader_agent.get_action(observation)
            logger.info(f"Leader step({leader_action})")
            (observation, reward, done, truncated, info) = environment.step(
                leader_action
            )
        else:
            follower_action = follower_agent.get_action(observation)
            logger.info(f"Follower step({follower_action})")
            (observation, reward, done, truncated, info) = environment.step(
                follower_action
            )
        print(f"Observation flattened: {observation.flatten()}")
    duration = time.time() - start
    # The game is over, so we can clean up the state machine.
    logger.info(f"Game over. Score: {turn_state['score']}")
    coordinator.Cleanup()
    return turn_state["score"], duration


def main(config_filepath="server/config/local-covers-config.yaml", instruction_uuid=""):
    nest_asyncio.apply()
    # Disabling most logs improves performance by about 50ms per game.
    logging.basicConfig(level=logging.INFO)
    config = ReadConfigOrDie(config_filepath)
    db_utils.ConnectToDatabase(config)
    scores = []
    durations = []
    coordinator = LocalGameCoordinator(config)
    for i in range(10):
        logger.info(
            f"========================== STARTING GAME {i} =========================="
        )
        score, duration = PlayGame(coordinator, instruction_uuid)
        logger.info(f"Game over. Score: {score}")
        scores.append(score)
        durations.append(duration)
    # Print out the scores.
    logger.warn(f"Mean score: {np.mean(scores)}")
    logger.warn(f"Mean duration: {np.mean(durations)}")

    # Plot a multi-figure diagram. On the left, scatter plot of game durations &
    # scores. On the right, show a histogram of scores.
    fig, (ax1, ax2) = plt.subplots(1, 2)
    ax1.scatter(durations, scores)
    ax1.set_xlabel("Duration")
    ax1.set_ylabel("Score")
    ax2.hist(scores)
    ax2.set_xlabel("Score")
    ax2.set_ylabel("Frequency")
    plt.show()


if __name__ == "__main__":
    fire.Fire(main)
