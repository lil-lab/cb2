from enum import Enum
from hex import HecsCoord

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields

import dateutil.parser

class FeedbackType(Enum):
    NONE = 0
    POSITIVE = 1
    NEGATIVE = 2

@dataclass_json
@dataclass(frozen=True)
class LiveFeedback(object):
    signal: FeedbackType = FeedbackType.NONE

def LiveFeedbackFromType(feedback_type):
    return LiveFeedback(feedback_type)