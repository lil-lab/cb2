from dataclasses import dataclass, field
from mashumaro.mixins.json import DataClassJSONMixin
from dataclasses_json import dataclass_json, config, LetterCase

from messages.rooms import Role


@dataclass
class ObjectiveMessage(DataClassJSONMixin):
    sender: Role = Role.NONE
    text: str = ""
    uuid: str = ""
    completed: bool = False
    cancelled: bool = False

@dataclass(frozen=True)
class ObjectiveCompleteMessage(DataClassJSONMixin):
    uuid: str = ""