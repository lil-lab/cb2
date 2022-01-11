from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from typing import List, Optional
from marshmallow import fields
from messages import message_to_server
from messages import message_from_server
from messages.rooms import Role
from remote_table import Remote

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
    message_from_server: message_from_server.MessageFromServer
    message_to_server: message_to_server.MessageToServer

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
    remotes: List[Remote]
    roles: List[Role]
    ids: List[int]