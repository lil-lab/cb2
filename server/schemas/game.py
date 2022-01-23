from hex import HecsCoord
from messages.action import Action
from schemas.mturk import *
from peewee import *
from schemas.clients import *

import datetime

class Game(BaseModel):
    id = AutoField()
    type = TextField() # 'game', 'lead_tutorial', or 'follow_tutorial'
    world_seed = TextField()
    leader = ForeignKeyField(Worker, backref='lead_games', null=True)
    follower = ForeignKeyField(Worker, backref='follow_games', null=True)
    number_cards = IntegerField(default=0)
    score = IntegerField(default=0)
    number_turns = IntegerField(default=0)
    start_time = DateTimeField(default=datetime.datetime.now)
    end_time = DateTimeField(default=datetime.datetime.max)
    completed = BooleanField(default=False)
    valid = BooleanField(default=True)  # Sqlite doesn't handle autoincrement so instead of deleting games, mark them as invalid.
    who_is_agent = TextField(default="")
    lead_assignment = ForeignKeyField(Assignment, backref='lead_games', null=True)
    follow_assignment = ForeignKeyField(Assignment, backref='follow_games', null=True)
    lead_remote = ForeignKeyField(Remote, backref='leader_games', null=True)
    follow_remote = ForeignKeyField(Remote, backref='follower_games', null=True)

class HecsCoordField(TextField):
    def db_value(self, value):
        return value.to_json()
    
    def python_value(self, db_val):
        return HecsCoord.from_json(db_val)

class ActionField(TextField):
    def db_value(self, value):
        return value.to_json()
    
    def python_value(self, db_val):
        return Action.from_json(db_val)

class Turn(BaseModel):
    game = ForeignKeyField(Game, backref='turns')
    role = TextField()  # 'Leader' or 'Follower'
    time = DateTimeField(default=datetime.datetime.now)
    turn_number = IntegerField(default=0)
    notes = TextField() # a CSV of 'UsedAllMoves', 'FinishedAllCommands', or 'RepeatedTurnNoInstructionsTodo'
    end_method = TextField() # Either 'RanOutOfTime' or 'UserPrompted'

class Instruction(BaseModel):
    game = ForeignKeyField(Game, backref='instructions')
    worker = ForeignKeyField(Worker, backref='moves', null=True)
    uuid = TextField()
    text = TextField()
    time = DateTimeField(default=datetime.datetime.now)
    instruction_number = IntegerField()
    turn_issued = IntegerField()
    turn_completed = IntegerField(default=-1)

class Move(BaseModel):
    game = ForeignKeyField(Game, backref='moves')
    instruction = ForeignKeyField(Instruction, backref='moves', null=True)
    character_role = TextField() # 'Leader' or 'Follower'
    worker = ForeignKeyField(Worker, backref='moves', null=True)
    turn_number = IntegerField()
    action = ActionField()
    position_before = HecsCoordField()
    game_time = TextField()
    server_time = DateTimeField()
    action_code = TextField()  # One of MF (Move Forward), MB (Move Backward), TR (Turn Right), TL (Turn Left). Or invalid if the action was not valid.