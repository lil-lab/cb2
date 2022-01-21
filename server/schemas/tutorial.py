from schemas.game import *
from schemas.mturk import *
from peewee import *
from schemas.clients import *

class FollowerTutorial(Game):
    remote = ForeignKeyField(Remote)
    start_time = DateTimeField(default=datetime.datetime.now)
    end_time = DateTimeField()
    assignment = ForeignKeyField(Assignment, backref='follower_tutorials')


class LeaderTutorial(Game):
    remote = ForeignKeyField(Remote)
    start_time = DateTimeField(default=datetime.datetime.now)
    end_time = DateTimeField()
    assignment = ForeignKeyField(Assignment, backref='leader_tutorials')
