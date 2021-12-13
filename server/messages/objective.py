from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase

from messages.rooms import Role


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass
class ObjectiveMessage:
    sender: Role = Role.NONE
    text: str = ""
    uuid: str = ""
    completed: bool = False

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class ObjectiveCompleteMessage:
    uuid: str = ""