from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from typing import List, Optional
from mashumaro.mixins.json import DataClassJSONMixin
from mashumaro import pass_through
from marshmallow import fields
from server.messages import message_to_server as mts
from server.messages import message_from_server as mfs
from server.messages.rooms import Role
from server.config import config as cfg

import dateutil

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
    message_from_server: mfs.MessageFromServer = field(default_factory=mfs.MessageFromServer)
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