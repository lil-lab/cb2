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


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class Room:
    name: str
    id: int
    capacity: int
    players: int
    locked: bool


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class RoomListing:
    servers: List[Room]


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class CreateRoomRequest:
    name: str
    capacity: int
    password: str


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class JoinRoomRequest:
    proposed_server: Room
    password: str


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class JoinRoomResponse:
    joined: bool


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class LeaveRoomNotice:
    """ Used to notify a user that they have left the room. 

        This is to allow the server to boot a player. Optionally,
        a reason can be left for the player explaining why.
    """
    reason: str


class RoomRequestType(Enum):
    """ Enumeration of the different types of management requests.  """
    NONE = 0
    LIST_ROOMS = 1
    CREATE_ROOM = 2
    JOIN_ROOM = 3
    LEAVE_ROOM = 4


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class RoomManagementRequest:
    type: RoomRequestType

    # Depending on the type above, the below are optionally populated.
    create_room: Optional[CreateRoomRequest]
    join_room: Optional[JoinRoomRequest]


class RoomResponseType(Enum):
    """ Enumeration of the different types of management responses.  """
    NONE = 0
    LIST_ROOMS = 1
    JOIN_ROOM_RESPONSE = 2
    LEAVE_NOTICE = 3

    # Depending on the type, the below are optionally populated.
    list_room: Optional[RoomListing]


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class RoomManagementResponse:
    type: RoomResponseType

    # Depending on the type above, the below are optionally populated.
    join_room: Optional[JoinRoomResponse]
    leave_notice: Optional[LeaveRoomNotice]
