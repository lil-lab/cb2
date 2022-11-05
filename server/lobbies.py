from typing import List, Tuple

from server.google_lobby import GoogleLobby
from server.lobby import Lobby, LobbyType
from server.mturk_lobby import MturkLobby
from server.open_lobby import OpenLobby

# Map from lobby name to lobby.
lobbies = {}


def InitializeLobbies(lobbies: List[Tuple[str, LobbyType]]):
    for (lobby_name, lobby_type) in lobbies:
        if lobby_type == LobbyType.NONE:
            continue
        CreateLobby(lobby_name, lobby_type)


def GetLobby(lobby_name: str) -> Lobby:
    return lobbies.get(lobby_name, None)


def GetLobbies() -> List[Lobby]:
    return list(lobbies.values())


def CreateLobby(lobby_name: str, lobby_type: LobbyType):
    if lobby_type == LobbyType.NONE:
        return
    elif lobby_type == LobbyType.MTURK:
        lobbies[lobby_name] = MturkLobby(lobby_name)
    elif lobby_type == LobbyType.OPEN:
        lobbies[lobby_name] = OpenLobby(lobby_name)
    elif lobby_type == LobbyType.GOOGLE:
        lobbies[lobby_name] = GoogleLobby(lobby_name)
    else:
        raise Exception(f"Lobby type not handled in CreateLobby(): {lobby_type}")
