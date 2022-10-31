from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin

from server.messages.rooms import Role


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
