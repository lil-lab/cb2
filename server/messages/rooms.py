""" This file contains game management messages.

Messages here allow you to enumerate the current games, join a game, or create a
new game.

"""

from enum import Enum
from hex import HecsCoord
from messages.map_update import MapUpdate

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from mashumaro.mixins.json import DataClassJSONMixin
from typing import List, Optional

import dateutil.parser


class Role(Enum):
    """ The role of a player in a game."""
    NONE = 0
    FOLLOWER = 1
    LEADER = 2


@dataclass(frozen=True)
class JoinResponse(DataClassJSONMixin):
    joined: bool

    place_in_queue: Optional[int]  # If joined == false.
    role: Role  # If joined == true.


@dataclass(frozen=True)
class LeaveRoomNotice(DataClassJSONMixin):
    """ Used to notify a user that they have left the room. 

        This is to allow the server to boot a player. Optionally,
        a reason can be left for the player explaining why.
    """
    reason: str


@dataclass(frozen=True)
class StatsResponse(DataClassJSONMixin):
    number_of_games: int
    players_in_game: int
    players_waiting: int


class RoomRequestType(Enum):
    """ Enumeration of the different types of management requests.  """
    NONE = 0
    STATS = 1
    JOIN = 2
    CANCEL = 3
    LEAVE = 4
    MAP_SAMPLE = 5


@dataclass(frozen=True)
class RoomManagementRequest(DataClassJSONMixin):
    type: RoomRequestType


class RoomResponseType(Enum):
    """ Enumeration of the different types of management responses.  """
    NONE = 0
    STATS = 1
    JOIN_RESPONSE = 2
    LEAVE_NOTICE = 3
    ERROR = 4
    MAP_SAMPLE = 5


@dataclass(frozen=True)
class RoomManagementResponse(DataClassJSONMixin):
    type: RoomResponseType

    # Depending on the type above, the below are optionally populated.
    stats: Optional[StatsResponse]
    join_response: Optional[JoinResponse]
    leave_notice: Optional[LeaveRoomNotice]
    map_update: Optional[MapUpdate] = None
    error: str = ""
