""" Defines message structure sent to server.  """

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

from mashumaro import pass_through
from mashumaro.mixins.json import DataClassJSONMixin

from server.messages.action import Action
from server.messages.google_auth import GoogleAuth
from server.messages.live_feedback import LiveFeedback
from server.messages.objective import ObjectiveCompleteMessage, ObjectiveMessage
from server.messages.pong import Pong
from server.messages.replay_messages import ReplayRequest
from server.messages.rooms import RoomManagementRequest
from server.messages.turn_state import TurnComplete
from server.messages.tutorials import TutorialRequest


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
    GOOGLE_AUTH = 10
    USER_INFO = 11
    REPLAY_REQUEST = 12
    SCENARIO_REQUEST = 13


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
    google_auth: Optional[GoogleAuth] = None
    replay_request: Optional[ReplayRequest] = None
