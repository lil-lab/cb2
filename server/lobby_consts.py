from dataclasses import dataclass
from enum import Enum

from mashumaro.mixins.json import DataClassJSONMixin


class LobbyType(Enum):
    NONE = 0
    MTURK = 1
    OPEN = 2
    GOOGLE = 3


@dataclass
class LobbyInfo(DataClassJSONMixin):
    name: str
    type: LobbyType
