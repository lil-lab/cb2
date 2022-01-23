import datetime
from peewee import *
from schemas.base import *

PREVIEW_ASSIGNMENT_ID = "ASSIGNMENT_ID_NOT_AVAILABLE"

"""
    Worker qual level is an integer that follows these rules:
    0 - No qualifications passed.
    1 - only follower tutorial passed.
    2 - only leader tutorial passed.
    3 - both tutorials passed.
    4 - only follower quiz passed.
    5 - only leader quiz passed.
    6 - quiz and tutorials passed. ready for playing.
    7+ increasing levels of "quality" of games not yet defined.
"""
class Worker(BaseModel):
    hashed_id = TextField()
    qual_level = IntegerField(default=0)

PREVIEW_ASSIGNMENT_ID = "ASSIGNMENT_ID_NOT_AVAILABLE"

class Assignment(BaseModel):
    assignment_id = TextField()
    worker = ForeignKeyField(Worker, backref='assignments')
    hit_id = TextField()
    submit_to_url = TextField()
    time_used = DateTimeField(default=datetime.datetime.now)