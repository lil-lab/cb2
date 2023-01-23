"""Scenarios allow the client to modify the game state to recreate certain situations."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from dataclasses_json import config
from mashumaro.mixins.json import DataClassJSONMixin

import server.hex as hex
from server.messages.map_update import MapUpdate
from server.messages.objective import ObjectiveMessage
from server.messages.prop import PropUpdate
from server.messages.rooms import Role
from server.messages.state_sync import StateSync
from server.messages.turn_state import TurnState


class TriggerType(Enum):
    NONE = 0
    LOCATION_REACHED = 1
    OBJECTIVE_COMPLETED = 2
    CARD_SET_COMPLETED = 3


@dataclass(frozen=True)
class Trigger(DataClassJSONMixin):
    uuid: str  # Uniquely identifying trigger string.
    type: TriggerType
    # The name of the trigger. This is used to identify the trigger.
    name: str
    # The actor role. This is used to identify the actor.
    actor_role: Role
    location: hex.HecsCoord
    objective: str  # The objective UUID that this trigger is for.


class TriggerReport(DataClassJSONMixin):
    uuid: str  # Uniquely identifying trigger string.
    type: TriggerType
    name: str
    actor_id: str
    location: hex.HecsCoord
    objective: str  # The objective UUID that this trigger is for.
    score: int  # The score achieved.


@dataclass(frozen=True)
class Scenario(DataClassJSONMixin):
    map: MapUpdate
    prop_update: PropUpdate
    turn_state: TurnState
    objectives: List[ObjectiveMessage]
    actor_state: StateSync


class ScenarioRequestType(Enum):
    NONE = 0
    # Changes the current state of the game to load a scenario. Clears any loaded triggers.
    LOAD_SCENARIO = 1
    # Ends the current scenario game.
    END_SCENARIO = 2
    # Registers a trigger. Scenarios are complete when a certain set of actions
    # has been completed. trigger must be populated in the scenario request.
    REGISTER_TRIGGER = 3
    # Unregisters a trigger. trigger_uuid must be populated in the scenario request.
    UNREGISTER_TRIGGER = 4


@dataclass(frozen=True)
class ScenarioRequest(DataClassJSONMixin):
    type: ScenarioRequestType
    scenario_data: Optional[str] = field(default=None)
    trigger: Optional[Trigger] = field(default=None)
    trigger_uuid: Optional[str] = field(default=None)


class ScenarioResponseType(Enum):
    NONE = 0
    LOADED = 1
    TRIGGER_REPORT = 2
    SCENARIO_DOWNLOAD = 3


def ExcludeIfNone(value):
    return value is None


@dataclass(frozen=True)
class ScenarioResponse(DataClassJSONMixin):
    type: ScenarioResponseType
    trigger_report: Optional[TriggerReport] = field(
        default=None, metadata=config(exclude=ExcludeIfNone)
    )
    scenario_download: Optional[str] = field(
        default=None, metadata=config(exclude=ExcludeIfNone)
    )
