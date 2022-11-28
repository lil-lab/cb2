"""A set of methods for registering and accessing lobbies"""
import logging
from typing import List

from server.follower_pilot_lobby import FollowerPilotLobby
from server.google_lobby import GoogleLobby
from server.lobby_consts import LobbyInfo, LobbyType
from server.mturk_lobby import MturkLobby
from server.open_lobby import OpenLobby

logger = logging.getLogger(__name__)

# Map from lobby name to lobby.
lobbies = {}


def InitializeLobbies(lobby_info: List[LobbyInfo]):
    for info in lobby_info:
        if info.type == LobbyType.NONE:
            continue
        CreateLobby(info.name, info.type, info.comment)


def GetLobby(lobby_name: str) -> "Lobby":
    return lobbies.get(lobby_name, None)


def GetLobbies() -> List["Lobby"]:
    return list(lobbies.values())


def CreateLobby(lobby_name: str, lobby_type: LobbyType, lobby_comment: str = ""):
    if lobby_type == LobbyType.MTURK:
        lobbies[lobby_name] = MturkLobby(lobby_name, lobby_comment)
    elif lobby_type == LobbyType.GOOGLE:
        lobbies[lobby_name] = GoogleLobby(lobby_name, lobby_comment)
    elif lobby_type == LobbyType.OPEN:
        lobbies[lobby_name] = OpenLobby(lobby_name, lobby_comment)
    elif lobby_type == LobbyType.FOLLOWER_PILOT:
        lobbies[lobby_name] = FollowerPilotLobby(lobby_name, lobby_comment)
    else:
        raise ValueError(f"Invalid lobby type: {lobby_type}")
