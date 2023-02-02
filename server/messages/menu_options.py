from dataclasses import dataclass, field
from enum import Enum
from typing import List

from mashumaro.mixins.json import DataClassJSONMixin


class ButtonCode(Enum):
    NONE = 0
    JOIN_QUEUE = 1
    LEAVE_QUEUE = 2
    JOIN_FOLLOWER_QUEUE = 3
    JOIN_LEADER_QUEUE = 4
    START_LEADER_TUTORIAL = 5
    START_FOLLOWER_TUTORIAL = 6


@dataclass
class ButtonDescriptor(DataClassJSONMixin):
    code: ButtonCode
    text: str
    tooltip: str


class MenuOptions(DataClassJSONMixin):
    buttons: List[ButtonDescriptor] = field(default_factory=list)
    bulletin_message: str
