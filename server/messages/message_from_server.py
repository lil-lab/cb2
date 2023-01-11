""" Defines message structure received from server.  """

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

import dateutil.parser
from dataclasses_json import config
from marshmallow import fields
from mashumaro.mixins.json import DataClassJSONMixin

from server.messages.action import Action
from server.messages.google_auth import GoogleAuthConfirmation
from server.messages.live_feedback import LiveFeedback
from server.messages.map_update import MapUpdate
from server.messages.objective import ObjectiveMessage
from server.messages.prop import Prop, PropUpdate
from server.messages.replay_messages import ReplayResponse
from server.messages.rooms import RoomManagementResponse
from server.messages.scenario import ScenarioResponse
from server.messages.state_sync import StateMachineTick, StateSync
from server.messages.turn_state import TurnState
from server.messages.tutorials import TutorialResponse
from server.messages.user_info import UserInfo


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
    GOOGLE_AUTH_CONFIRMATION = 11
    USER_INFO = 12
    # Triggers a prop spawn on the client
    PROP_SPAWN = 13
    # Used for signaling that a card set has been collected. The indicated props
    # will disappear on the client.
    PROP_DESPAWN = 14
    # Used for starting/stopping replays, relaying replay state.
    REPLAY_RESPONSE = 15
    # Used for starting/stopping/controlling scenario rooms.
    SCENARIO_RESPONSE = 16


def ActionsFromServer(actions):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.ACTIONS,
        actions,
        None,
        None,
        None,
        None,
        None,
        None,
    )


def MapUpdateFromServer(map_update):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.MAP_UPDATE,
        None,
        map_update,
        None,
        None,
        None,
        None,
        None,
    )


def StateSyncFromServer(state_sync):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.STATE_SYNC,
        None,
        None,
        state_sync,
        None,
        None,
        None,
        None,
    )


def RoomResponseFromServer(room_response):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.ROOM_MANAGEMENT,
        None,
        None,
        None,
        room_response,
        None,
        None,
        None,
    )


def ObjectivesFromServer(texts: List[ObjectiveMessage]):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.OBJECTIVE,
        None,
        None,
        None,
        None,
        texts,
        None,
        None,
    )


def GameStateFromServer(game_state):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.GAME_STATE,
        None,
        None,
        None,
        None,
        None,
        game_state,
        None,
    )


def TutorialResponseFromServer(tutorial_response):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.TUTORIAL_RESPONSE,
        None,
        None,
        None,
        None,
        None,
        None,
        tutorial_response,
    )


def PingMessageFromServer():
    return MessageFromServer(
        datetime.utcnow(), MessageType.PING, None, None, None, None, None, None, None
    )


def LiveFeedbackFromServer(feedback):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.LIVE_FEEDBACK,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        feedback,
    )


def PropUpdateFromServer(props: PropUpdate):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.PROP_UPDATE,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        props,
    )


def StateMachineTickFromServer(state_machine_tick):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.STATE_MACHINE_TICK,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        state_machine_tick,
    )


def GoogleAuthConfirmationFromServer(google_auth_confirmation):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.GOOGLE_AUTH_CONFIRMATION,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        google_auth_confirmation,
    )


def UserInfoFromServer(user_info):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.USER_INFO,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        user_info,
    )


def PropSpawnFromServer(prop):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.PROP_SPAWN,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        prop,
    )


def PropDespawnFromServer(props):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.PROP_DESPAWN,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        props,
    )


def ReplayResponseFromServer(replay_response):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.REPLAY_RESPONSE,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        replay_response,
    )


def ScenarioResponseFromServer(scenario_response):
    return MessageFromServer(
        datetime.utcnow(),
        MessageType.SCENARIO_RESPONSE,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        scenario_response,
    )


def ExcludeIfNone(value):
    return value is None


@dataclass(frozen=True)
class MessageFromServer(DataClassJSONMixin):
    transmit_time: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=dateutil.parser.isoparse,
            mm_field=fields.DateTime(format="iso"),
        )
    )
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
    google_auth_confirmation: Optional[
        GoogleAuthConfirmation
    ] = GoogleAuthConfirmation()
    user_info: Optional[UserInfo] = UserInfo()
    prop_spawn: Optional[Prop] = field(
        default=None, metadata=config(exclude=ExcludeIfNone)
    )
    prop_despawn: Optional[List[Prop]] = field(
        default=None, metadata=config(exclude=ExcludeIfNone)
    )
    replay_response: Optional[ReplayResponse] = field(
        default=None, metadata=config(exclude=ExcludeIfNone)
    )
    scenario_response: Optional[ScenarioResponse] = field(
        default=None, metadata=config(exclude=ExcludeIfNone)
    )
