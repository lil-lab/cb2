from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase

from messages.rooms import Role


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class TextMessage:
    sender: Role = Role.NONE
    text: str = ""
