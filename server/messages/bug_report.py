from dataclasses import dataclass
from typing import List

from mashumaro.mixins.json import DataClassJSONMixin

from server.messages.map_update import MapUpdate
from server.messages.state_sync import StateSync
from server.messages.turn_state import TurnState


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
