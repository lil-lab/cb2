"""Scenarios allow the client to modify the game state to recreate certain situations."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from dataclasses_json import config
from mashumaro.mixins.json import DataClassJSONMixin

from cb2game.server.messages.live_feedback import LiveFeedback
from cb2game.server.messages.map_update import MapUpdate
from cb2game.server.messages.objective import ObjectiveMessage
from cb2game.server.messages.prop import PropUpdate
from cb2game.server.messages.state_sync import StateSync
from cb2game.server.messages.turn_state import TurnState


@dataclass(frozen=True)
class Scenario(DataClassJSONMixin):
    scenario_id: str  # Unique identifier for the scenario. Used to attach to a scenario.
    map: Optional[MapUpdate] = field(default=None)
    prop_update: Optional[PropUpdate] = field(default=None)
    turn_state: Optional[TurnState] = field(default=None)
    objectives: Optional[List[ObjectiveMessage]] = field(default=None)
    actor_state: Optional[StateSync] = field(default=None)
    kvals: Dict[str, str] = field(default_factory=dict)
    live_feedback: List[LiveFeedback] = field(default_factory=list)
    # A list of card IDs that must be selected to complete the scenario. If empty, normal game
    # play is allowed.
    target_card_ids: Optional[List[int]] = None
    # Duration of the scenario, by default.
    duration_s: float = 3600.0


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
