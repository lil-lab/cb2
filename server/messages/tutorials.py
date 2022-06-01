""" Defines tutorial messages. """
from enum import Enum
from messages.action import Action
from messages.rooms import RoomManagementRequest, Role
from messages.objective import ObjectiveMessage, ObjectiveCompleteMessage
from messages.turn_state import TurnComplete

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import date
from datetime import datetime
from hex import HecsCoord
from marshmallow import fields
from typing import List, Optional

import dateutil.parser
import logging
import typing

logger = logging.getLogger()

class FollowerActions(Enum):
    NONE = 0
    FORWARDS = 1
    BACKWARDS = 2
    TURN_LEFT = 3
    TURN_RIGHT = 4

class TooltipType(Enum):
    NONE = 0
    # The tooltip disappears after the user clicks on the "Ok" button on the tooltip text window or hits shift.
    UNTIL_DISMISSED = 1
    # The tooltip disappears once the player has sent a message.
    UNTIL_MESSAGE_SENT = 2
    UNTIL_CAMERA_TOGGLED = 3
    UNTIL_INDICATOR_REACHED = 4
    UNTIL_OBJECTIVES_COMPLETED = 5
    UNTIL_SET_COLLECTED = 6
    UNTIL_TURN_ENDED = 7
    FOLLOWER_TURN = 8

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class Tooltip:
    highlighted_component_tag: str
    text: str
    type: TooltipType

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class Indicator:
    location: HecsCoord

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class Instruction:
    text: str

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class TutorialStep:
    indicator: Indicator
    tooltip: Tooltip
    instruction: Instruction
    other_player_turn: List[FollowerActions] = None

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class TutorialComplete:
    tutorial_name: str
    completion_date: str

class TutorialRequestType(Enum):
    NONE = 0
    START_TUTORIAL = 1
    REQUEST_NEXT_STEP = 2


class TutorialResponseType(Enum):
    NONE = 0
    STARTED = 1
    STEP = 2
    COMPLETE = 3


LEADER_TUTORIAL = "leader_tutorial"
FOLLOWER_TUTORIAL = "follower_tutorial"

def RoleFromTutorialName(tutorial_name):
    if tutorial_name == LEADER_TUTORIAL:
        return Role.LEADER
    elif tutorial_name == FOLLOWER_TUTORIAL:
        return Role.FOLLOWER
    else:
        logger.warn(f"Received invalid tutorial name: {tutorial_name}")
        return Role.NONE

@dataclass_json
@dataclass(frozen=True)
class TutorialRequest:
    type: TutorialRequestType
    tutorial_name: str

@dataclass_json
@dataclass(frozen=True)
class TutorialResponse:
    type: TutorialResponseType
    tutorial_name: str
    step: TutorialStep
    complete: TutorialComplete

def TutorialCompletedResponse(tutorial_name):
    return TutorialResponse(TutorialResponseType.COMPLETE, tutorial_name, None, TutorialComplete(tutorial_name, str(date.today())))

def TutorialResponseFromStep(tutorial_name, step):
    return TutorialResponse(TutorialResponseType.STEP, tutorial_name, step, None)
