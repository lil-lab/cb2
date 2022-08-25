""" Defines message structure received from server.  """

from server.messages import live_feedback
from server.messages.action import Action
from server.messages.turn_state import TurnState
from server.messages.state_sync import StateSync, StateMachineTick
from server.messages.map_update import MapUpdate
from server.messages.rooms import RoomManagementResponse
from server.messages.objective import ObjectiveMessage
from server.messages.tutorials import TutorialResponse
from server.messages.live_feedback import LiveFeedback
from server.messages.prop import PropUpdate

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from enum import Enum
from mashumaro.mixins.json import DataClassJSONMixin
from marshmallow import fields
from typing import List, Optional

import dateutil.parser

class MessageType(Enum):
    ACTIONS = 0
    MAP_UPDATE = 1
    STATE_SYNC = 2
    ROOM_MANAGEMENT = 3
    OBJECTIVE = 4
    GAME_STATE = 5
    TUTORIAL_RESPONSE = 6
    PING = 7
    LIVE_FEEDBACK = 8
    PROP_UPDATE = 9
    STATE_MACHINE_TICK = 10

def ActionsFromServer(actions):
    return MessageFromServer(datetime.utcnow(), MessageType.ACTIONS, actions, None, None, None, None, None, None)

def MapUpdateFromServer(map_update):
    return MessageFromServer(datetime.utcnow(), MessageType.MAP_UPDATE, None, map_update, None, None, None, None, None)

def StateSyncFromServer(state_sync):
    return MessageFromServer(datetime.utcnow(), MessageType.STATE_SYNC, None, None, state_sync, None, None, None, None)

def RoomResponseFromServer(room_response):
    return MessageFromServer(datetime.utcnow(), MessageType.ROOM_MANAGEMENT, None, None, None, room_response, None, None, None)

def ObjectivesFromServer(texts):
    return MessageFromServer(datetime.utcnow(), MessageType.OBJECTIVE, None, None, None, None, texts, None, None)

def GameStateFromServer(game_state):
    return MessageFromServer(datetime.utcnow(), MessageType.GAME_STATE, None, None, None, None, None, game_state, None)

def TutorialResponseFromServer(tutorial_response):
    return MessageFromServer(datetime.utcnow(), MessageType.TUTORIAL_RESPONSE, None, None, None, None, None, None, tutorial_response)

def PingMessageFromServer():
    return MessageFromServer(datetime.utcnow(), MessageType.PING, None, None, None, None, None, None, None)

def LiveFeedbackFromServer(feedback):
    return MessageFromServer(datetime.utcnow(), MessageType.LIVE_FEEDBACK, None, None, None, None, None, None, None, feedback)

def PropUpdateFromServer(props):
    return MessageFromServer(datetime.utcnow(), MessageType.PROP_UPDATE, None, None, None, None, None, None, None, None, props)

def StateMachineTickFromServer(state_machine_tick):
    return MessageFromServer(datetime.utcnow(), MessageType.STATE_MACHINE_TICK, None, None, None, None, None, None, None, None, None, state_machine_tick)

@dataclass(frozen=True)
class MessageFromServer(DataClassJSONMixin):
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
    objectives: Optional[List[ObjectiveMessage]]
    turn_state: Optional[TurnState]
    tutorial_response: Optional[TutorialResponse]
    live_feedback: Optional[LiveFeedback] = LiveFeedback()
    prop_update: Optional[PropUpdate] = PropUpdate()
    state_machine_tick: Optional[StateMachineTick] = StateMachineTick()