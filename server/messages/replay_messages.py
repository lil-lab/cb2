from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from dataclasses_json import config
from mashumaro import pass_through
from mashumaro.mixins.json import DataClassJSONMixin


class Command(Enum):
    NONE = 0
    PLAY = 1
    PAUSE = 2
    PREVIOUS = 3
    NEXT = 4
    RESET = 5
    REPLAY_SPEED = 6


@dataclass(frozen=True)
class ReplayInfo(DataClassJSONMixin):
    game_id: int
    start_time: datetime = field(
        metadata={"deserialize": "pendulum", "serialize": pass_through}
    )
    paused: bool
    tick: int
    total_ticks: int
    turn: int
    total_turns: int
    # When the message was sent in the original game.
    transmit_time: datetime = field(
        metadata={"deserialize": "pendulum", "serialize": pass_through}
    )
    percent_complete: float = 0


class ReplayRequestType(Enum):
    NONE = 0
    START_REPLAY = 1
    REPLAY_COMMAND = 2


@dataclass(frozen=True)
class ReplayRequest(DataClassJSONMixin):
    type: ReplayRequestType
    game_id: int = -1
    command: Optional[Command] = Command.NONE
    # Only valid if type == REPLAY_COMMAND and command == REPLAY_SPEED
    replay_speed: float = 1


class ReplayResponseType(Enum):
    NONE = 0
    REPLAY_STARTED = 1
    REPLAY_INFO = 2


def ExcludeIfNone(value):
    return value is None


@dataclass(frozen=True)
class ReplayResponse(DataClassJSONMixin):
    type: ReplayResponseType
    info: Optional[ReplayInfo] = field(
        default=None, metadata=config(exclude=ExcludeIfNone)
    )
