from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from messages.rooms import Role
from datetime import datetime
from marshmallow import fields

import dateutil.parser


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class GameState:
    turn: Role
    turns_remaining: int
    moves_remaining: int  # Number of moves remaining.
    game_end_date: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=dateutil.parser.isoparse,
            mm_field=fields.DateTime(format='iso')
        ))
    score: int
