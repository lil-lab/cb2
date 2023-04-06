from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from mashumaro.mixins.json import DataClassJSONMixin

from server.messages.rooms import Role


class QuestionType(Enum):
    NONE = 0
    BOOLEAN = 1
    MULTIPLE_CHOICE = 2
    TEXT = 3


@dataclass(frozen=True)
class FeedbackQuestion(DataClassJSONMixin):
    type: QuestionType = QuestionType.NONE
    to: Role = ""  # To whom the question is directed
    question: str = ""
    uuid: str = field(default_factory=lambda: str(uuid4()))
    timeout_s: float = field(default=10.0)
    # Time sent to the client, in seconds since the epoch. GMT time.
    transmit_time_s: float = field(default=0.0)
    # Valid for type MULTIPLE_CHOICE only
    answers: list = field(default_factory=list)


class FeedbackResponse(DataClassJSONMixin):
    uuid: str = ""
    # Valid for type TEXT only
    response: str = ""
    # Valid for type MULTIPLE_CHOICE only
    response_index: int = -1
    # Valid for type BOOLEAN true/false only
    response_tf: bool = False
