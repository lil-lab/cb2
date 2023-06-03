"""Scenarios allow the client to modify the game state to recreate certain situations."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from dataclasses_json import config
from mashumaro.mixins.json import DataClassJSONMixin

from server.messages.live_feedback import LiveFeedback
from server.messages.map_update import MapUpdate
from server.messages.objective import ObjectiveMessage
from server.messages.prop import PropUpdate
from server.messages.state_sync import StateSync
from server.messages.turn_state import TurnState


@dataclass(frozen=True)
class Scenario(DataClassJSONMixin):
    scenario_id: str  # Unique identifier for the scenario. Used to attach to a scenario.
    map: MapUpdate
    prop_update: PropUpdate
    turn_state: TurnState
    objectives: List[ObjectiveMessage]
    actor_state: StateSync
    kvals: Dict[str, str] = field(default_factory=dict)
    live_feedback: List[LiveFeedback] = field(default_factory=list)


class ScenarioRequestType(Enum):
    NONE = 0
    # Changes the current state of the game to load a scenario.
    LOAD_SCENARIO = 1
    # Ends the current scenario game.
    END_SCENARIO = 2
    # Attached to an existing scenario. scenario_id must be populated in the scenario request.
    ATTACH_TO_SCENARIO = 5


@dataclass(frozen=True)
class ScenarioRequest(DataClassJSONMixin):
    type: ScenarioRequestType
    scenario_data: Optional[str] = field(default=None)
    scenario_id: Optional[str] = field(default=None)


class ScenarioResponseType(Enum):
    NONE = 0
    LOADED = 1
    SCENARIO_DOWNLOAD = 3


def ExcludeIfNone(value):
    return value is None


@dataclass(frozen=True)
class ScenarioResponse(DataClassJSONMixin):
    type: ScenarioResponseType
    scenario_download: Optional[str] = field(
        default=None, metadata=config(exclude=ExcludeIfNone)
    )
