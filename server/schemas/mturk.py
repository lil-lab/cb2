import datetime
from typing import Text
import orjson

from peewee import *
from schemas.base import *

class RecentScoresField(TextField):
    def __init__(self, *args, **kwargs):
        super().__init__(default="[]", *args, **kwargs)

    def db_value(self, value):
        return orjson.dumps(value, option=orjson.OPT_NAIVE_UTC).decode('utf-8')
    
    def python_value(self, db_val):
        return orjson.loads(db_val)

"""
    This table is used to track the performance of each worker as they play and improve.
"""
class WorkerExperience(BaseModel):
    lead_games_played = IntegerField(default=0)
    lead_score_sum = IntegerField(default=0)
    lead_score_avg = IntegerField(default=0)

    follow_games_played = IntegerField(default=0)
    follow_score_sum = IntegerField(default=0)
    follow_score_avg = IntegerField(default=0)

    total_score_avg = IntegerField(default=0)
    total_score_sum = IntegerField(default=0)
    total_games_played = IntegerField(default=0)

    last_100_lead_scores = RecentScoresField()
    last_100_follow_scores = RecentScoresField()
    last_100_scores = RecentScoresField()

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
    experience = ForeignKeyField(WorkerExperience, backref='worker', null=True)

PREVIEW_ASSIGNMENT_ID = "ASSIGNMENT_ID_NOT_AVAILABLE"

class Assignment(BaseModel):
    assignment_id = TextField()
    worker = ForeignKeyField(Worker, backref='assignments')
    hit_id = TextField()
    submit_to_url = TextField()
    time_used = DateTimeField(default=datetime.datetime.utcnow)