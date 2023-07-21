from enum import Enum


class Role(Enum):
    """The role of a player in a game."""

    NONE = 0
    FOLLOWER = 1
    LEADER = 2
    # Used for scenario rooms to load scenarios and observe game state.
    SPECTATOR = 3
    # Used when the game is paused, to indicate that neither role is active.
    PAUSED = 4
    # Used when the game is temporarily paused (with timeout) to question the follower.
    QUESTIONING_FOLLOWER = 5
    MAX = 10
