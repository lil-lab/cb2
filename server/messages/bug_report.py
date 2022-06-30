from enum import Enum
from modulefinder import Module
from hex import HecsCoord

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from mashumaro.mixins.json import DataClassJSONMixin
from marshmallow import fields
from messages.map_update import MapUpdate
from messages.turn_state import TurnState
from messages.state_sync import StateSync
from typing import List, Optional

import dateutil.parser

@dataclass(frozen=True)
class ModuleLog(DataClassJSONMixin):
    module: str
    log: str

@dataclass(frozen=True)
class BugReport(DataClassJSONMixin):
    map_update: MapUpdate
    turn_state_log: List[TurnState]
    state_sync: StateSync
    logs: List[ModuleLog]