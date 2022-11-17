import uuid
from enum import IntEnum

from peewee import *

from server.schemas.base import *
from server.schemas.mturk import WorkerExperience

"""
    User qual level is an integer that follows these rules:
    0 - No qualifications passed.
    1 - only follower qual.
    2 - follower & leader qual.
    3 - Expert qual.
"""


class UserQualLevel(IntEnum):
    NONE = 0
    FOLLOWER = 1
    LEADER = 2
    EXPERT = 3


class GoogleUser(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    hashed_google_id = TextField()  # Use sha256 hash of google id.
    qual_level = IntegerField(default=0)
    experience = ForeignKeyField(WorkerExperience, backref="google_user", null=True)
    kv_store = TextField(default="{}")
