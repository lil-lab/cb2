from enum import Enum
from modulefinder import Module
from hex import HecsCoord

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from messages.map_update import MapUpdate
from messages.turn_state import TurnState
from messages.state_sync import StateSync
from typing import List, Optional

import dateutil.parser

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class ModuleLog:
    module: str
    log: str

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class BugReport:
    map_update: MapUpdate
    turn_state_log: List[TurnState]
    state_sync: StateSync
    logs: List[ModuleLog]