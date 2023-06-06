from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from py_client.game_endpoint import Action, GameState
from server.messages.rooms import Role

if TYPE_CHECKING:
    pass


class Agent(ABC):
    """A generic interface for an agent that can play a game.

    The game endpoint API specifies a step() function which takes in an action
    and returns the next game state.  The agent provides the next action to
    take, given a game state.

    """

    @abstractmethod
    def choose_action(
        self, game_state: GameState, action_mask: Optional[List[bool]] = None
    ) -> Action:
        """Chooses the next action to take, given a game state.

        Actions can be optionally masked out, by providing a mask. Agent may or
        may not support action_masking.  If None, then no masking is done.

        """
        ...

    @abstractmethod
    def role(self) -> Role:
        """Returns the role of the agent."""
        ...
