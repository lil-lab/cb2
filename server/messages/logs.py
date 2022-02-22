from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from typing import List, Optional
from marshmallow import fields
from messages import message_to_server as mts
from messages import message_from_server as mfs
from messages.rooms import Role
from remote_table import Remote
from config import config as cfg

import dateutil

class Direction(Enum):
    NONE = 0
    TO_SERVER = 1
    FROM_SERVER = 2

def LogEntryFromIncomingMessage(player_id, message_to_server):
    return LogEntry(Direction.TO_SERVER, player_id, None, message_to_server)


def LogEntryFromOutgoingMessage(player_id, message_from_server):
    return LogEntry(Direction.FROM_SERVER, player_id, message_from_server, None)

@dataclass_json
@dataclass(frozen=True)
class LogEntry:
    message_direction: Direction
    player_id: int
    message_from_server: mfs.MessageFromServer = field(default_factory=mfs.MessageFromServer)
    message_to_server: mts.MessageToServer = field(default_factory=mts.MessageToServer)

@dataclass_json
@dataclass(frozen=True)
class GameInfo:
    start_time: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=dateutil.parser.isoparse,
            mm_field=fields.DateTime(format='iso')
        ))
    game_id: int
    game_name: str
    roles: List[Role]
    ids: List[int]

@dataclass_json
@dataclass
class GameLog(object):
    game_info: GameInfo
    log_entries: List[LogEntry]
    server_config: cfg.Config = field(default_factory=cfg.Config)