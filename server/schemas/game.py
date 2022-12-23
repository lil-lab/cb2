import datetime
import json

import orjson
from peewee import *

from server.messages.action import Action
from server.schemas.base import *
from server.schemas.clients import *
from server.schemas.google_user import GoogleUser
from server.schemas.mturk import *
from server.schemas.util import HecsCoordField


class Game(BaseModel):
    id = AutoField()
    # type is: [<lobby-name>|<lobby-type>|]<game-type>. game-type:'game', 'lead_tutorial', or 'follow_tutorial'.
    type = TextField(null=True)
    log_directory = TextField(null=True)  # Directory where logs are stored.
    world_seed = TextField(null=True)
    leader = ForeignKeyField(Worker, backref="lead_games", null=True)
    follower = ForeignKeyField(Worker, backref="follow_games", null=True)
    google_leader = ForeignKeyField(GoogleUser, backref="lead_games", null=True)
    google_follower = ForeignKeyField(GoogleUser, backref="follow_games", null=True)
    number_cards = IntegerField(default=0)
    score = IntegerField(default=0)
    number_turns = IntegerField(default=0)
    start_time = DateTimeField(default=datetime.datetime.utcnow)
    end_time = DateTimeField(default=datetime.datetime.max)
    completed = BooleanField(default=False)
    valid = BooleanField(
        default=True
    )  # Sqlite doesn't handle autoincrement so instead of deleting games, mark them as invalid.
    who_is_agent = TextField(default="")
    lead_assignment = ForeignKeyField(Assignment, backref="lead_games", null=True)
    follow_assignment = ForeignKeyField(Assignment, backref="follow_games", null=True)
    lead_remote = ForeignKeyField(Remote, backref="leader_games", null=True)
    follow_remote = ForeignKeyField(Remote, backref="follower_games", null=True)
    server_software_commit = TextField(null=False, default="")
    kvals = TextField(null=True)  # JSON of key-value pairs.


class ActionField(TextField):
    def db_value(self, value):
        return orjson.dumps(
            value,
            option=orjson.OPT_NAIVE_UTC | orjson.OPT_PASSTHROUGH_DATETIME,
            default=datetime.datetime.isoformat,
        ).decode("utf-8")

    def python_value(self, db_val):
        return Action.from_json(db_val)


class Turn(BaseModel):
    game = ForeignKeyField(Game, backref="turns")
    role = TextField()  # 'Leader' or 'Follower'
    time = DateTimeField(default=datetime.datetime.utcnow)
    turn_number = IntegerField(default=0)
    notes = (
        TextField()
    )  # a CSV of 'UsedAllMoves', 'FinishedAllCommands', or 'SkippedTurnNoInstructionsTodo'
    end_method = (
        TextField()
    )  # Something like 'RanOutOfTime' or 'UserPrompted', or 'FollowerOutOfMoves', 'FollowerFinishedInstructions', or 'UserPromptedInterruption'


class Instruction(BaseModel):
    game = ForeignKeyField(Game, backref="instructions")
    worker = ForeignKeyField(Worker, backref="moves", null=True)
    uuid = TextField()
    text = TextField()
    time = DateTimeField(default=datetime.datetime.utcnow)
    instruction_number = IntegerField()
    turn_issued = IntegerField()
    turn_activated = IntegerField(default=-1)
    turn_completed = IntegerField(default=-1)
    turn_cancelled = IntegerField(default=-1)

    def dict(self):
        return {
            "game": self.game_id,
            "worker": self.worker_id,
            "uuid": self.uuid,
            "text": self.text,
            "time": self.time.isoformat(),
            "instruction_number": self.instruction_number,
            "turn_issued": self.turn_issued,
            "turn_completed": self.turn_completed,
            "turn_cancelled": self.turn_cancelled,
        }


class Move(BaseModel):
    game = ForeignKeyField(Game, backref="moves")
    instruction = ForeignKeyField(Instruction, backref="moves", null=True)
    character_role = TextField()  # 'Role.LEADER' or 'Role.FOLLOWER'
    worker = ForeignKeyField(Worker, backref="moves", null=True)
    turn_number = IntegerField()
    action = ActionField()
    position_before = HecsCoordField()
    game_time = TextField()
    server_time = DateTimeField()
    # `action_code` is one of MF (Move Forward), MB (Move Backward), TR (Turn
    # Right), TL (Turn Left), DONE. Or invalid if the action was not valid.
    action_code = TextField()
    orientation_before = IntegerField()

    def dict(self):
        return {
            "game": self.game_id,
            "instruction": self.instruction_id,
            "character_role": self.character_role,
            "worker": self.worker,
            "turn_number": self.turn_number,
            "action": json.dumps(self.action, default=str),
            "position_before": self.position_before,
            "game_time": self.game_time,
            "server_time": self.server_time.isoformat(),
            "action_code": self.action_code,
            "orientation_before": self.orientation_before,
        }


class LiveFeedback(BaseModel):
    game = ForeignKeyField(Game, backref="feedbacks")
    feedback_type = TextField()
    instruction = ForeignKeyField(Instruction, backref="feedbacks", null=True)
    turn_number = IntegerField()
    follower_position = HecsCoordField()
    follower_orientation = FloatField()
    game_time = TextField()
    server_time = DateTimeField()

    def dict(self):
        return {
            "game": self.game_id,
            "feedback_type": self.feedback_type,
            "instruction": self.instruction.uuid,
            "turn_number": self.turn_number,
            "follower_position": self.follower_position,
            "follower_orientation": self.follower_orientation,
            "game_time": self.game_time,
            "server_time": self.server_time.isoformat(),
        }
