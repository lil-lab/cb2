""" Defines message structure sent to server.  """

from enum import Enum
from messages.action import Action
from messages.rooms import RoomManagementRequest
from messages.objective import ObjectiveMessage, ObjectiveCompleteMessage
from messages.turn_state import TurnComplete

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from typing import List, Optional

import dateutil.parser
import typing


class MessageType(Enum):
    ACTIONS = 0
    STATE_SYNC_REQUEST = 1
    ROOM_MANAGEMENT = 2
    OBJECTIVE = 3
    OBJECTIVE_COMPLETED = 4
    TURN_COMPLETE = 5


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class MessageToServer:
    transmit_time: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=dateutil.parser.isoparse,
            mm_field=fields.DateTime(format='iso')
        ))
    type: MessageType
    actions: Optional[List[Action]]
    room_request: Optional[RoomManagementRequest]
    objective: Optional[ObjectiveMessage] = ObjectiveMessage("")
    objective_complete: Optional[ObjectiveCompleteMessage] = ObjectiveCompleteMessage("")
    turn_complete: Optional[TurnComplete] = TurnComplete()
