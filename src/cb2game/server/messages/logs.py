from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List

from mashumaro import pass_through
from mashumaro.mixins.json import DataClassJSONMixin

from cb2game.server.config import config as cfg
from cb2game.server.messages import message_from_server as mfs
from cb2game.server.messages import message_to_server as mts
from cb2game.server.messages.rooms import Role


class Direction(Enum):
    NONE = 0
    TO_SERVER = 1
    FROM_SERVER = 2


def LogEntryFromIncomingMessage(player_id, message_to_server):
    return LogEntry(Direction.TO_SERVER, player_id, None, message_to_server)


def LogEntryFromOutgoingMessage(player_id, message_from_server):
    return LogEntry(Direction.FROM_SERVER, player_id, message_from_server, None)


@dataclass(frozen=True)
class LogEntry(DataClassJSONMixin):
    message_direction: Direction
    player_id: int
    message_from_server: mfs.MessageFromServer = field(
        default_factory=mfs.MessageFromServer
    )
    message_to_server: mts.MessageToServer = field(default_factory=mts.MessageToServer)


@dataclass(frozen=True)
class GameInfo(DataClassJSONMixin):
    start_time: datetime = field(
        metadata={"deserialize": "pendulum", "serialize": pass_through}
    )
    game_id: int
    game_name: str
    roles: List[Role]
    ids: List[int]


@dataclass
class GameLog(DataClassJSONMixin):
    game_info: GameInfo
    log_entries: List[LogEntry]
    server_config: cfg.Config = field(default_factory=cfg.Config)
