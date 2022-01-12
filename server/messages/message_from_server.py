""" Defines message structure received from server.  """

from enum import Enum
from messages.action import Action
from messages.turn_state import TurnState
from messages.state_sync import StateSync
from messages.map_update import MapUpdate
from messages.rooms import RoomManagementResponse
from messages.objective import ObjectiveMessage
from messages.tutorials import TutorialResponse

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
    ROOM_MANAGEMENT = 3
    OBJECTIVE = 4
    GAME_STATE = 5
    TUTORIAL_RESPONSE = 6


def ActionsFromServer(actions):
    return MessageFromServer(datetime.now(), MessageType.ACTIONS, actions, None, None, None, None, None, None)


def MapUpdateFromServer(map_update):
    return MessageFromServer(datetime.now(), MessageType.MAP_UPDATE, None, map_update, None, None, None, None, None)


def StateSyncFromServer(state_sync):
    return MessageFromServer(datetime.now(), MessageType.STATE_SYNC, None, None, state_sync, None, None, None, None)


def RoomResponseFromServer(room_response):
    return MessageFromServer(datetime.now(), MessageType.ROOM_MANAGEMENT, None, None, None, room_response, None, None, None)


def ObjectivesFromServer(texts):
    return MessageFromServer(datetime.now(), MessageType.OBJECTIVE, None, None, None, None, texts, None, None)


def GameStateFromServer(game_state):
    return MessageFromServer(datetime.now(), MessageType.GAME_STATE, None, None, None, None, None, game_state, None)

def TutorialResponseFromServer(tutorial_response):
    return MessageFromServer(datetime.now(), MessageType.TUTORIAL_RESPONSE, None, None, None, None, None, None, tutorial_response)

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
    objectives: Optional[List[ObjectiveMessage]]
    turn_state: Optional[TurnState]
    tutorial_response: Optional[TutorialResponse]
