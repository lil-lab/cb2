from dataclasses import dataclass
from enum import Enum

from mashumaro.mixins.json import DataClassJSONMixin


class FeedbackType(Enum):
    NONE = 0
    POSITIVE = 1
    NEGATIVE = 2
    MAX = 3


@dataclass(frozen=True)
class LiveFeedback(DataClassJSONMixin):
    signal: FeedbackType = FeedbackType.NONE


def LiveFeedbackFromType(feedback_type):
    return LiveFeedback(feedback_type)
