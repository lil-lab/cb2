from dataclasses import dataclass
from enum import IntEnum

from mashumaro.mixins.json import DataClassJSONMixin


class LobbyType(IntEnum):
    NONE = 0
    MTURK = 1
    OPEN = 2
    GOOGLE = 3


def LobbyTypeFromString(data):
    if data == "LobbyType.MTURK":
        return LobbyType.MTURK
    if data == "LobbyType.OPEN":
        return LobbyType.OPEN
    if data == "LobbyType.GOOGLE":
        return LobbyType.GOOGLE
    return LobbyType.NONE


@dataclass
class LobbyInfo(DataClassJSONMixin):
    name: str
    type: LobbyType
