import datetime
from peewee import *
from server.schemas.base import *
from server.schemas.mturk import Worker

class Username(BaseModel):
    username = TextField()
    worker = ForeignKeyField(Worker, backref='username')

class Leaderboard(BaseModel):
    time = DateTimeField(default=datetime.datetime.utcnow)
    score = IntegerField()
    leader = ForeignKeyField(Worker, null=True, backref='leaderboard_entries')
    follower = ForeignKeyField(Worker, null=True, backref='leaderboard_entries')
