import datetime

from peewee import *

from cb2game.server.schemas.base import *
from cb2game.server.schemas.google_user import GoogleUser
from cb2game.server.schemas.lobby import LobbyTypeField
from cb2game.server.schemas.mturk import Worker


class Username(BaseModel):
    username = TextField()
    worker = ForeignKeyField(Worker, backref="username", null=True)
    user = ForeignKeyField(GoogleUser, backref="username", null=True)


class Leaderboard(BaseModel):
    time = DateTimeField(default=datetime.datetime.utcnow)
    score = IntegerField()
    lobby_name = TextField()
    lobby_type = LobbyTypeField()
    # The entries below for leader/follower are dynamic and hard to resolve. These provide a simple text summary of the leader/follower for display.
    leader_name = TextField(default="")
    follower_name = TextField(default="")
    # Depending on lobby type, either mturk_* or google_* will be populated. For bot-sandbox, neither may.
    mturk_leader = ForeignKeyField(
        Worker, null=True, backref="lobby_leaderboard_entries"
    )
    mturk_follower = ForeignKeyField(
        Worker, null=True, backref="lobby_leaderboard_entries"
    )
    google_leader = ForeignKeyField(
        GoogleUser, null=True, backref="lobby_leaderboard_entries"
    )
    google_follower = ForeignKeyField(
        GoogleUser, null=True, backref="lobby_leaderboard_entries"
    )
