from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

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
    def choose_action(self, game_state: GameState) -> Action:
        """Chooses the next action to take, given a game state."""
        ...

    @abstractmethod
    def role(self) -> Role:
        """Returns the role of the agent."""
        ...


class AgentType(Enum):
    NONE = 0
    PILOT_FOLLOWER = 1
    GPT_FOLLOWER = 2

    def __str__(self):
        return self.name

    @staticmethod
    def from_str(s: str):
        return AgentType[s]
