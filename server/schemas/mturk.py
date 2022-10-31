import datetime
from enum import IntEnum

import orjson
from peewee import *

from server.schemas.base import *


class RecentScoresField(TextField):
    def __init__(self, *args, **kwargs):
        super().__init__(default="", *args, **kwargs)

    def db_value(self, value):
        return orjson.dumps(value, option=orjson.OPT_NAIVE_UTC).decode("utf-8")

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

    last_1k_lead_scores = RecentScoresField()
    last_1k_follow_scores = RecentScoresField()
    last_1k_scores = RecentScoresField()

    # Deferred to resolve the circular dependency (game -> worker (lead/follower) -> worker_experience -> game)
    last_lead = DeferredForeignKey("Game", null=True, deferrable="INITIALLY DEFERRED")
    last_follow = DeferredForeignKey("Game", null=True, deferrable="INITIALLY DEFERRED")
    last_game = DeferredForeignKey("Game", null=True, deferrable="INITIALLY DEFERRED")


"""
    Worker qual level is an integer that follows these rules:
    0 - No qualifications passed.
    1 - only follower qual.
    2 - follower & leader qual.
    3 - Expert qual.
"""


class WorkerQualLevel(IntEnum):
    NONE = 0
    FOLLOWER = 1
    LEADER = 2
    EXPERT = 3


class Worker(BaseModel):
    hashed_id = TextField()
    qual_level = IntegerField(default=0)
    experience = ForeignKeyField(WorkerExperience, backref="worker", null=True)


PREVIEW_ASSIGNMENT_ID = "ASSIGNMENT_ID_NOT_AVAILABLE"


class Assignment(BaseModel):
    assignment_id = TextField()
    worker = ForeignKeyField(Worker, backref="assignments")
    hit_id = TextField()
    submit_to_url = TextField()
    time_used = DateTimeField(default=datetime.datetime.utcnow)
