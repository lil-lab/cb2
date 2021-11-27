from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class TextMessage:
    text: str
