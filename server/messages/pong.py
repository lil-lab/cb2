from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from mashumaro.mixins.json import DataClassJSONMixin
from marshmallow import fields
from server.messages import action
from typing import Optional

import dateutil.parser

@dataclass(frozen=True)
class Pong(DataClassJSONMixin):
    ping_receive_time: str = ""