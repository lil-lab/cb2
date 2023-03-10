from dataclasses import dataclass
from enum import IntEnum

from mashumaro.mixins.json import DataClassJSONMixin


class LobbyType(IntEnum):
    NONE = 0
    MTURK = 1
    OPEN = 2
    GOOGLE = 3
    FOLLOWER_PILOT = 4
    REPLAY = 5
    SCENARIO = 6
    GOOGLE_LEADER = 7


def IsMturkLobby(lobby_type):
    return lobby_type in [LobbyType.MTURK, LobbyType.FOLLOWER_PILOT]


def IsGoogleLobby(lobby_type):
    return lobby_type in [LobbyType.GOOGLE, LobbyType.GOOGLE_LEADER]


def LobbyTypeFromString(data):
    if data == "LobbyType.MTURK":
        return LobbyType.MTURK
    if data == "LobbyType.OPEN":
        return LobbyType.OPEN
    if data == "LobbyType.GOOGLE":
        return LobbyType.GOOGLE
    if data == "LobbyType.FOLLOWER_PILOT":
        return LobbyType.FOLLOWER_PILOT
    if data == "LobbyType.REPLAY":
        return LobbyType.REPLAY
    if data == "LobbyType.SCENARIO":
        return LobbyType.SCENARIO
    if data == "LobbyType.GOOGLE_LEADER":
        return LobbyType.GOOGLE_LEADER
    return LobbyType.NONE


@dataclass
class LobbyInfo(DataClassJSONMixin):
    name: str
    type: LobbyType
    comment: str = ""
    # The maximum number of games that can be created in this lobby.
    game_capacity: int = 40
