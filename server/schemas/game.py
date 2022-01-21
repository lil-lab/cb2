from hex import HecsCoord
from messages.action import Action
from schemas.mturk import *
from peewee import *
from schemas.clients import *

import datetime

class Game(BaseModel):
    game_id = AutoField()
    world_seed = TextField()
    leader = ForeignKeyField(Worker, backref='lead_games')
    follower = ForeignKeyField(Worker, backref='follow_games')
    number_cards = IntegerField()
    score = IntegerField()
    start_time = DateTimeField(default=datetime.datetime.now)
    end_time = DateTimeField()
    valid = BooleanField()  # Sqlite doesn't handle autoincrement so instead of deleting games, mark them as invalid.
    who_is_agent = TextField()
    leader_assignment = ForeignKeyField(Assignment, backref='lead_games')
    follower_assignment = ForeignKeyField(Assignment, backref='follow_games')

class HecsCoordField(Field):
    field_type = 'HecsCoord'

    def db_value(self, value):
        value.to_json()
    
    def python_value(self, db_val):
        return HecsCoord.from_json(db_val)

class ActionField(Field):
    field_type = 'HecsCoord'

    def db_value(self, value):
        value.to_json()
    
    def python_value(self, db_val):
        return Action.from_json(db_val)

class Turn(BaseModel):
    game = ForeignKeyField(Game, backref='turns')
    role = TextField()  # 'Leader' or 'Follower'
    time = DateTimeField(default=datetime.datetime.now)
    end_method = TextField() # 'RanOutOfMoves', 'RanOutOfTime', or 'FinishedAllCommands'

class Instruction(BaseModel):
    game = ForeignKeyField(Game, backref='instructions')
    remote = ForeignKeyField(Remote, backref='moves')
    instruction_text = TextField()
    instruction_number = IntegerField()

class Move(BaseModel):
    game = ForeignKeyField(Game, backref='moves')
    instruction = ForeignKeyField(Instruction, backref='moves')
    character_role = TextField() # 'Leader' or 'Follower'
    remote = ForeignKeyField(Remote, backref='moves')
    move_number = IntegerField()
    action = ActionField()
    position = HecsCoordField()
    game_time = TextField()
    server_time = DateTimeField()
