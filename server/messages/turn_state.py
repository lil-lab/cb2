from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from messages.rooms import Role
from datetime import datetime
from marshmallow import fields

import dateutil.parser


def GameOverMessage(game_start_date, sets_collected, score, turn_number):
    return TurnState(Role.NONE, 0, 0, datetime.now(), game_start_date, sets_collected, score, True, turn_number)


def TurnUpdate(turn_role, moves_remaining, turns_left, turn_end, game_start, sets_collected, score, turn_number):
    return TurnState(turn_role, moves_remaining, turns_left, turn_end, game_start, sets_collected, score, False, turn_number)

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass
class TurnState:
    turn: Role
    moves_remaining: int  # Number of moves remaining this turn.
    turns_left: int # Number of turns until the game ends.
    turn_end: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=dateutil.parser.isoparse,
            mm_field=fields.DateTime(format='iso')
        ))
    game_start: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=dateutil.parser.isoparse,
            mm_field=fields.DateTime(format='iso')
        ))
    sets_collected: int
    score: int
    game_over: bool
    turn_number: int

@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass(frozen=True)
class TurnComplete:
    pass