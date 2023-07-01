from peewee import *

from cb2game.server.schemas.base import *
from cb2game.server.schemas.mturk import *


class Remote(BaseModel):
    hashed_ip = TextField()
    remote_port = IntegerField()
    worker = ForeignKeyField(Worker, backref="remotes", null=True)
    assignment = ForeignKeyField(Assignment, backref="assignment", null=True)


class ConnectionEvents(BaseModel):
    remote = ForeignKeyField(Remote, backref="connection_events")
    timestamp = DateTimeField(default=datetime.datetime.utcnow)
    event_type = TextField()
