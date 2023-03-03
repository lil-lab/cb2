import logging

LEADER_MOVES_PER_TURN = 5
FOLLOWER_MOVES_PER_TURN = 10

LEADER_SECONDS_PER_TURN = 50
FOLLOWER_SECONDS_PER_TURN = 15

FOLLOWER_TURN_END_DELAY_SECONDS = 1

logger = logging.getLogger(__name__)


def turn_reward(score):
    """Calculates the turn reward (# of turns added) for a given score."""
    if score == 0:
        return 5
    elif score in [1, 2]:
        return 4
    elif score in [3, 4]:
        return 3
    elif score in [5, 6]:
        return 2
    elif score in [7, 8]:
        return 1
    else:
        return 0


def cumulative_turns_added(score):
    """Calculates the cumulative extra turns added since the start of the game for a given score."""
    turns = 0
    for i in range(score):
        turns += turn_reward(i)
    return turns
