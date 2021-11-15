""" Defines message structure received from server.  """

from enum import Enum
from messages.action import Action
from messages.state_sync import StateSync
from messages.map_update import MapUpdate
from messages.rooms import RoomManagementResponse

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from typing import List, Optional

import dateutil.parser
import typing


class MessageType(Enum):
    ACTIONS = 0
    MAP_UPDATE = 1
    STATE_SYNC = 2
    ROOM_MANAGEMENT_RESPONSE = 3


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class MessageFromServer:
    transmit_time: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=dateutil.parser.isoparse,
            mm_field=fields.DateTime(format='iso')
        ))
    type: MessageType
    actions: Optional[List[Action]]
    map_update: Optional[MapUpdate]
    state: Optional[StateSync]
    room_management_response: Optional[RoomManagementResponse]
