"""A set of methods for registering and accessing lobbies"""
import logging
from typing import List

from server.lobbies.follower_pilot_lobby import FollowerPilotLobby
from server.lobbies.google_leader_lobby import GoogleLeaderLobby
from server.lobbies.google_lobby import GoogleLobby
from server.lobbies.mturk_lobby import MturkLobby
from server.lobbies.open_lobby import OpenLobby
from server.lobbies.replay_lobby import ReplayLobby
from server.lobbies.scenario_lobby import ScenarioLobby
from server.lobby_consts import LobbyInfo, LobbyType

logger = logging.getLogger(__name__)

# Map from lobby name to lobby.
lobbies = {}


def InitializeLobbies(lobby_info: List[LobbyInfo]):
    for info in lobby_info:
        if info.type == LobbyType.NONE:
            continue
        CreateLobby(info)


def GetLobby(lobby_name: str) -> "Lobby":
    return lobbies.get(lobby_name, None)


def GetLobbies() -> List["Lobby"]:
    return list(lobbies.values())


def CreateLobby(info: LobbyInfo):
    if info.type == LobbyType.MTURK:
        lobbies[info.name] = MturkLobby(info)
    elif info.type == LobbyType.GOOGLE:
        lobbies[info.name] = GoogleLobby(info)
    elif info.type == LobbyType.OPEN:
        lobbies[info.name] = OpenLobby(info)
    elif info.type == LobbyType.FOLLOWER_PILOT:
        lobbies[info.name] = FollowerPilotLobby(info)
    elif info.type == LobbyType.REPLAY:
        lobbies[info.name] = ReplayLobby(info)
    elif info.type == LobbyType.SCENARIO:
        lobbies[info.name] = ScenarioLobby(info)
    elif info.type == LobbyType.GOOGLE_LEADER:
        lobbies[info.name] = GoogleLeaderLobby(info)
    else:
        raise ValueError(f"Invalid lobby type: {info.type}")
