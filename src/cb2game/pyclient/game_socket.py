from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Tuple

from cb2game.server.messages import message_from_server, message_to_server

""" This interface abstracts over communication between remote and local CB2 games.

    Low-level interface for sending and receiving messages.

    The implementations are in remote_client.py and local_game_coordinator.py.
    RemoteSocket is used to communicate with a game running on a remote server
    over the network, and LocalSocket is used to communicate with a local game
    running in the same process.
"""


class GameSocket(ABC):
    @abstractmethod
    def send_message(self, message: message_to_server.MessageToServer):
        """Send a message to the server. Blocking."""
        ...

    @abstractmethod
    def connected(self) -> bool:
        """Is the socket connected to a server or state machine?"""
        ...

    @abstractmethod
    def receive_message(
        self, timeout: timedelta
    ) -> Tuple[message_from_server.MessageFromServer, str]:
        """Blocks until a message is received or the timeout is reached."""
        ...
