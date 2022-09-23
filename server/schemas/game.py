from importlib.machinery import FrozenImporter
from server.hex import HecsCoord
from server.messages.action import Action
from server.schemas.mturk import *
from peewee import *
from server.schemas.clients import *

import orjson

import datetime

class Game(BaseModel):
    id = AutoField()
    type = TextField(null=True) # 'game', 'lead_tutorial', or 'follow_tutorial'
    log_directory = TextField(null=True) # Directory where logs are stored.
    world_seed = TextField(null=True)
    leader = ForeignKeyField(Worker, backref='lead_games', null=True)
    follower = ForeignKeyField(Worker, backref='follow_games', null=True)
    number_cards = IntegerField(default=0)
    score = IntegerField(default=0)
    number_turns = IntegerField(default=0)
    start_time = DateTimeField(default=datetime.datetime.utcnow)
    end_time = DateTimeField(default=datetime.datetime.max)
    completed = BooleanField(default=False)
    valid = BooleanField(default=True)  # Sqlite doesn't handle autoincrement so instead of deleting games, mark them as invalid.
    who_is_agent = TextField(default="")
    lead_assignment = ForeignKeyField(Assignment, backref='lead_games', null=True)
    follow_assignment = ForeignKeyField(Assignment, backref='follow_games', null=True)
    lead_remote = ForeignKeyField(Remote, backref='leader_games', null=True)
    follow_remote = ForeignKeyField(Remote, backref='follower_games', null=True)
    server_software_commit = TextField(null=False, default="")

class HecsCoordField(TextField):
    def db_value(self, value):
        return orjson.dumps(value, option=orjson.OPT_NAIVE_UTC).decode('utf-8')
    
    def python_value(self, db_val):
        return HecsCoord.from_json(db_val)

class ActionField(TextField):
    def db_value(self, value):
        return orjson.dumps(value, option=orjson.OPT_NAIVE_UTC | orjson.OPT_PASSTHROUGH_DATETIME, default=datetime.datetime.isoformat).decode('utf-8')
    
    def python_value(self, db_val):
        return Action.from_json(db_val)

class InitialState(BaseModel):
    game = ForeignKeyField(Game, backref='initial_state', null=True)
    time = DateTimeField(default=datetime.datetime.utcnow)
    leader_id = IntegerField()  # In-game ID of the leader.
    follower_id = IntegerField() # In-game ID of the follower.
    leader_position = HecsCoordField()
    leader_rotation_degrees = IntegerField()
    follower_position = HecsCoordField()
    follower_rotation_degrees = IntegerField()

class Turn(BaseModel):
    game = ForeignKeyField(Game, backref='turns')
    role = TextField()  # 'Leader' or 'Follower'
    time = DateTimeField(default=datetime.datetime.utcnow)
    turn_number = IntegerField(default=0)
    notes = TextField() # a CSV of 'UsedAllMoves', 'FinishedAllCommands', or 'SkippedTurnNoInstructionsTodo'
    end_method = TextField() # Something like 'RanOutOfTime' or 'UserPrompted', or 'FollowerOutOfMoves', 'FollowerFinishedInstructions', or 'UserPromptedInterruption'

def InstructionTurnActive(instruction):
    game = instruction.game
    instruction_before_query = Instruction.select().where(Instruction.game == game, Instruction.time < instruction.time).order_by(Instruction.time.desc())
    if instruction_before_query.count() == 0:
        return 0
    instruction_before = instruction_before_query.get()
    if instruction_before.turn_completed == -1:
        return instruction_before.turn_cancelled
    return instruction_before.turn_completed

class Instruction(BaseModel):
    game = ForeignKeyField(Game, backref='instructions')
    worker = ForeignKeyField(Worker, backref='moves', null=True)
    uuid = TextField()
    text = TextField()
    time = DateTimeField(default=datetime.datetime.utcnow)
    instruction_number = IntegerField()
    turn_issued = IntegerField()
    turn_completed = IntegerField(default=-1)
    turn_cancelled = IntegerField(default=-1)

class Move(BaseModel):
    game = ForeignKeyField(Game, backref='moves')
    instruction = ForeignKeyField(Instruction, backref='moves', null=True)
    character_role = TextField() # 'Role.LEADER' or 'Role.FOLLOWER'
    worker = ForeignKeyField(Worker, backref='moves', null=True)
    turn_number = IntegerField()
    action = ActionField()
    position_before = HecsCoordField()
    game_time = TextField()
    server_time = DateTimeField()
    action_code = TextField()  # One of MF (Move Forward), MB (Move Backward), TR (Turn Right), TL (Turn Left). Or invalid if the action was not valid.
    orientation_before = IntegerField()

class LiveFeedback(BaseModel):
    game = ForeignKeyField(Game, backref='feedbacks')
    feedback_type = TextField()
    instruction = ForeignKeyField(Instruction, backref='feedbacks', null=True)
    turn_number = IntegerField()
    follower_position = HecsCoordField()
    follower_orientation = FloatField()
    game_time = TextField()
    server_time = DateTimeField()
