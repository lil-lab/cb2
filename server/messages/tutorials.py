""" Defines tutorial messages. """
import logging
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import List

from mashumaro.mixins.json import DataClassJSONMixin

from server.hex import HecsCoord
from server.messages.rooms import Role

logger = logging.getLogger()


class FollowerActions(Enum):
    NONE = 0
    FORWARDS = 1
    BACKWARDS = 2
    TURN_LEFT = 3
    TURN_RIGHT = 4
    INSTRUCTION_DONE = 5
    END_TURN = 6


class TooltipType(Enum):
    NONE = 0
    # The tooltip disappears after the user clicks on the "Ok" button on the tooltip text window or hits shift.
    UNTIL_DISMISSED = 1
    # The tooltip disappears once the player has sent a message.
    UNTIL_MESSAGE_SENT = 2
    UNTIL_CAMERA_TOGGLED = 3
    # Only valid if there's exactly 1 indicator.
    UNTIL_INDICATOR_REACHED = 4
    UNTIL_OBJECTIVES_COMPLETED = 5
    UNTIL_SET_COLLECTED = 6
    UNTIL_TURN_ENDED = 7
    FOLLOWER_TURN = 8
    UNTIL_POSITIVE_FEEDBACK = 9
    UNTIL_NEGATIVE_FEEDBACK = 10


@dataclass(frozen=True)
class Tooltip(DataClassJSONMixin):
    highlighted_component_tag: str
    text: str
    type: TooltipType


@dataclass(frozen=True)
class Indicator(DataClassJSONMixin):
    location: HecsCoord


@dataclass(frozen=True)
class Instruction(DataClassJSONMixin):
    text: str


@dataclass(frozen=True)
class TutorialStep(DataClassJSONMixin):
    indicators: List[Indicator]
    tooltip: Tooltip
    instruction: Instruction
    other_player_turn: List[FollowerActions] = None


@dataclass(frozen=True)
class TutorialComplete(DataClassJSONMixin):
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


@dataclass(frozen=True)
class TutorialRequest(DataClassJSONMixin):
    type: TutorialRequestType
    tutorial_name: str


@dataclass(frozen=True)
class TutorialResponse(DataClassJSONMixin):
    type: TutorialResponseType
    tutorial_name: str
    step: TutorialStep
    complete: TutorialComplete


def TutorialCompletedResponse(tutorial_name):
    return TutorialResponse(
        TutorialResponseType.COMPLETE,
        tutorial_name,
        None,
        TutorialComplete(tutorial_name, str(date.today())),
    )


def TutorialResponseFromStep(tutorial_name, step):
    return TutorialResponse(TutorialResponseType.STEP, tutorial_name, step, None)
