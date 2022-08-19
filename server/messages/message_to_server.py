""" Defines message structure sent to server.  """

from enum import Enum
from mashumaro import pass_through
from mashumaro.mixins.json import DataClassJSONMixin
from server.messages.action import Action
from server.messages.rooms import RoomManagementRequest
from server.messages.live_feedback import LiveFeedback
from server.messages.objective import ObjectiveMessage, ObjectiveCompleteMessage
from server.messages.pong import Pong
from server.messages.turn_state import TurnComplete
from server.messages.tutorials import TutorialRequest, TutorialRequestType

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from typing import List, Optional

import dateutil.parser
import typing
import pendulum


class MessageType(Enum):
    ACTIONS = 0
    STATE_SYNC_REQUEST = 1
    ROOM_MANAGEMENT = 2
    OBJECTIVE = 3
    OBJECTIVE_COMPLETED = 4
    TURN_COMPLETE = 5
    TUTORIAL_REQUEST = 6
    PONG = 7
    LIVE_FEEDBACK = 8
    CANCEL_PENDING_OBJECTIVES = 9


@dataclass(frozen=True)
class MessageToServer(DataClassJSONMixin):
    transmit_time: datetime = field(
        metadata={"deserialize": "pendulum", "serialize": pass_through}
    )
    type: MessageType = MessageType.ACTIONS
    actions: Optional[List[Action]] = None
    room_request: Optional[RoomManagementRequest] = None
    objective: Optional[ObjectiveMessage] = None
    objective_complete: Optional[ObjectiveCompleteMessage] = None
    turn_complete: Optional[TurnComplete] = None
    tutorial_request: Optional[TutorialRequest] = None
    pong: Optional[Pong] = None
    live_feedback: Optional[LiveFeedback] = None