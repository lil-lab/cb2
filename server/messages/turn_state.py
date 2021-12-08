from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from messages.rooms import Role
from datetime import datetime
from marshmallow import fields

import dateutil.parser


def GameOverMessage(start_time, sets_collected, score):
    game_duration = datetime.now() - start_time
    sec = game_duration.seconds
    minutes = (sec // 60)
    seconds_remaining = sec - minutes * 60
    duration_str = f"{minutes}m{seconds_remaining}s"
    return TurnState(Role.NONE, 0, datetime.now(), duration_str, sets_collected, score, True)


def TurnUpdate(turn_role, moves_remaining, game_end_date, start_time, sets_collected, score):
    game_duration = datetime.now() - start_time
    sec = game_duration.seconds
    minutes = (sec // 60)
    seconds_remaining = sec - minutes * 60
    duration_str = f"{minutes}m{seconds_remaining}s"
    return TurnState(turn_role, moves_remaining, game_end_date, duration_str, sets_collected, score, False)


@dataclass_json(letter_case=LetterCase.PASCAL)
@dataclass
class TurnState:
    turn: Role
    moves_remaining: int  # Number of moves remaining.
    game_end_date: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=dateutil.parser.isoparse,
            mm_field=fields.DateTime(format='iso')
        ))
    game_duration: str
    sets_collected: int
    score: int
    game_over: bool
