from dataclasses import dataclass, field
from typing import List, Optional

from mashumaro.mixins.json import DataClassJSONMixin

from cb2game.server.messages.map_update import MapUpdate
from cb2game.server.messages.state_sync import StateSync
from cb2game.server.messages.turn_state import TurnState


@dataclass(frozen=True)
class ModuleLog(DataClassJSONMixin):
    module: str
    log: str


@dataclass(frozen=True)
class BugReport(DataClassJSONMixin):
    logs: List[ModuleLog]
    turn_state_log: List[TurnState] = field(default_factory=list)
    state_sync: Optional[StateSync] = None
    map_update: Optional[MapUpdate] = None
