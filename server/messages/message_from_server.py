""" Defines message structure received from server.  """
 
from enum import Enum
from .action import Action
from .state_sync import StateSync
from .map_update import MapUpdate

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from typing import List, Optional

import dateutil.parser
import typing

class MessageType(Enum):
     ACTIONS = 0
     MAP_UPDATE = 1
     STATE_SYNC = 2

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class MessageFromServer:
    transmit_time: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=datetime.fromisoformat,
            mm_field=fields.DateTime(format='iso')
        )
    )
    type: MessageType
    actions: Optional[List[Action]]
    map_update: Optional[MapUpdate]
    state: Optional[StateSync]
