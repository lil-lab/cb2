""" This file contains game management messages.

Messages here allow you to enumerate the current games, join a game, or create a
new game.

"""

from enum import Enum
from hex import HecsCoord

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from typing import List, Optional

import dateutil.parser


class Role(Enum):
    """ The role of a player in a game. """
    NONE = 0
    FOLLOWER = 1
    LEADER = 2


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class JoinResponse:
    joined: bool

    place_in_queue: Optional[int]  # If joined == false.
    role: Role  # If joined == true.


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class LeaveRoomNotice:
    """ Used to notify a user that they have left the room. 

        This is to allow the server to boot a player. Optionally,
        a reason can be left for the player explaining why.
    """
    reason: str


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class StatsResponse:
    number_of_games: int
    players_in_game: int
    followers_waiting: int
    leaders_waiting: int


class RoomRequestType(Enum):
    """ Enumeration of the different types of management requests.  """
    NONE = 0
    STATS = 1
    JOIN = 2
    LEAVE = 3


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class RoomManagementRequest:
    type: RoomRequestType


class RoomResponseType(Enum):
    """ Enumeration of the different types of management responses.  """
    NONE = 0
    STATS = 1
    JOIN_RESPONSE = 2
    LEAVE_NOTICE = 3
    ERROR = 4


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class RoomManagementResponse:
    type: RoomResponseType

    # Depending on the type above, the below are optionally populated.
    stats: Optional[StatsResponse]
    join_response: Optional[JoinResponse]
    leave_notice: Optional[LeaveRoomNotice]
