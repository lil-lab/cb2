from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from messages import action
from typing import Optional

import dateutil.parser

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class Pong:
    ping_receive_time: str = ""