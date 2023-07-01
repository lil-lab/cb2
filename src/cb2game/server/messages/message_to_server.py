""" Defines message structure sent to server.  """

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

from mashumaro import pass_through
from mashumaro.mixins.json import DataClassJSONMixin

from cb2game.server.messages.action import Action
from cb2game.server.messages.client_exception import ClientException
from cb2game.server.messages.google_auth import GoogleAuth
from cb2game.server.messages.live_feedback import LiveFeedback
from cb2game.server.messages.objective import ObjectiveCompleteMessage, ObjectiveMessage
from cb2game.server.messages.pong import Pong
from cb2game.server.messages.replay_messages import ReplayRequest
from cb2game.server.messages.rooms import RoomManagementRequest
from cb2game.server.messages.scenario import ScenarioRequest
from cb2game.server.messages.turn_state import TurnComplete
from cb2game.server.messages.tutorials import TutorialRequest


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
    # Only good for scenario rooms. Enables control of scenarios.
    SCENARIO_REQUEST = 13
    # Ok in any room. Asks the server to download current game state as a scenario.
    SCENARIO_DOWNLOAD = 14
    FEEDBACK_RESPONSE = 15
    CLIENT_EXCEPTION = 16


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
    scenario_request: Optional[ScenarioRequest] = None
    client_exception: Optional[ClientException] = None
