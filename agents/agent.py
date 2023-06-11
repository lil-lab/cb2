from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    pass


from py_client.game_endpoint import Action, GameState, Role


class Agent(ABC):
    """CB2 agent interface.

    Implement this interface and register it in agents/config.py to create your own
    CB2 agent.

    Use agents/remote_agent.py to connect to a remote server (like CB2.ai), or
    agents/local_agent_pair.py for local self-training.
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

    @abstractmethod
    def thoughts(self) -> str:
        """Returns the thoughts of the agent.

        This is used for logging the "thought" stage of chain-of-thought agents.
        Other agents can just use the default implementation (an empty string).
        """
        return ""
