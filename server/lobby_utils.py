"""A set of methods for registering and accessing lobbies"""
from typing import List

from server.google_lobby import GoogleLobby
from server.lobby_consts import LobbyInfo, LobbyType
from server.mturk_lobby import MturkLobby
from server.open_lobby import OpenLobby

# Map from lobby name to lobby.
lobbies = {}


def InitializeLobbies(lobby_info: List[LobbyInfo]):
    for info in lobby_info:
        if info.type == LobbyType.NONE:
            continue
        CreateLobby(info.name, info.type)


def GetLobby(lobby_name: str) -> "Lobby":
    return lobbies.get(lobby_name, None)


def GetLobbies() -> List["Lobby"]:
    return list(lobbies.values())


def CreateLobby(lobby_name: str, lobby_type: LobbyType):
    if lobby_type == LobbyType.MTURK:
        lobbies[lobby_name] = MturkLobby(lobby_name)
    elif lobby_type == LobbyType.GOOGLE:
        lobbies[lobby_name] = GoogleLobby(lobby_name)
    elif lobby_type == LobbyType.OPEN:
        lobbies[lobby_name] = OpenLobby(lobby_name)
    else:
        raise ValueError(f"Invalid lobby type: {lobby_type}")
