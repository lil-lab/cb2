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
    # JSON string of key value pairs. Used for storing user data.
    # Known key/val pairs:
    # "leader_tutorial": bool
    # "follower_tutorial": bool
    kv_store = TextField(
        default='{"leader_tutorial": false, "follower_tutorial": false}'
    )


def GetOrCreateGoogleUser(hashed_user_id):
    user_query = (
        GoogleUser.select()
        .join(WorkerExperience, join_type=JOIN.LEFT_OUTER)
        .where(GoogleUser.hashed_google_id == hashed_user_id)
    )
    if user_query.count() == 0:
        user = GoogleUser.create(hashed_google_id=hashed_user_id)
        user.save()
    else:
        user = user_query.get()
    return user


def GetGoogleUser(hashed_user_id):
    user_query = (
        GoogleUser.select()
        .join(WorkerExperience, join_type=JOIN.LEFT_OUTER)
        .where(GoogleUser.hashed_google_id == hashed_user_id)
    )
    if user_query.count() == 0:
        logger.warning(
            f"User {hashed_user_id} does not exist in the database. Skipping."
        )
        return None
    user = user_query.get()
    return user
