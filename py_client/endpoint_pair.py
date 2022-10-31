""" Wrapper class which allows for local self-play. """
import logging

from py_client.game_endpoint import Action, Role

logger = logging.getLogger(__name__)


class EndpointPair:
    """Wraps two endpoints connected to the same game in a single object."""

    def __init__(self, coordinator, game_name):
        """Creates & manages two endpoints which are connected to the same local game."""
        self._leader = coordinator.JoinGame(game_name)
        self._follower = coordinator.JoinGame(game_name)
        self.coordinator = coordinator
        self.game_name = game_name
        self._initial_state = None
        self.turn = None

    def initialize(self):
        """Initializes the game endpoints. Must be called once."""
        self._leader.Initialize()
        self._follower.Initialize()
        assert self._leader.initialized(), "Leader failed to initialize."
        assert self._follower.initialized(), "Follower failed to initialize."
        initial_state = self._leader.initial_state()
        _, _, turn_state, _, _, _ = initial_state
        if turn_state.turn == Role.LEADER:
            self._initial_state = initial_state
        else:
            self._initial_state = self._follower.initial_state()
        self.turn = turn_state.turn

    # Used to retrieve action masks for the leader and follower.
    def leader_mask(self):
        """Returns action mask for the leader.

        Returns:
            A list of booleans, where True indicates that the corresponding action is valid.
        """
        return self._leader.action_mask()

    def follower_mask(self):
        """Returns action mask for the follower.

        Returns:
            A list of booleans, where True indicates that the corresponding action is valid.
        """
        return self._follower.action_mask()

    # Deprecated -- Gives low-level access to underlying endpoint objects.
    def leader(self):
        """Returns the leader endpoint. Discouraged, use step() instead."""
        return self._leader

    def follower(self):
        """Returns the follower endpoint. Discouraged, use step() instead."""
        return self._follower

    def over(self):
        """Returns true if the game is over."""
        return self._leader.over() or self._follower.over()

    def score(self):
        """Returns the game score."""
        return self._leader.score()

    def duration(self):
        """Returns game duration as a timedelta object."""
        return self._leader.game_duration()

    def initial_state(self):
        """Returns the initial state of the game. If already previously called, returns None."""
        state = self._initial_state
        self._initial_state = None
        return state

    def step(self, action):
        """Takes a single step in the game."""
        if self.turn == Role.LEADER:
            leader_result = self._leader.step(action, wait_for_turn=False)
            _, _, turn_state, _, _, _ = leader_result
            follower_result = self._follower.step(
                Action.NoopAction(), wait_for_turn=False
            )
            self.turn = turn_state.turn
        elif self.turn == Role.FOLLOWER:
            follower_result = self._follower.step(action, wait_for_turn=False)
            _, _, turn_state, _, _, _ = follower_result
            leader_result = self._leader.step(Action.NoopAction(), wait_for_turn=False)
            self.turn = turn_state.turn
        else:
            raise Exception(f"Invalid turn state {self.turn}.")
        if self.turn == Role.LEADER:
            return leader_result
        return follower_result
