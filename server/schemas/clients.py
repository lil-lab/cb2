from peewee import *
from schemas.base import *
from schemas.game import *
from schemas.mturk import *

class Remote(BaseModel):
    hashed_remote_ip = TextField()
    remote_port = IntegerField()
    worker = ForeignKeyField(Worker, backref='remotes')

class ConnectionEvents(BaseModel):
    remote = ForeignKeyField(Remote, backref='connection_events')
    timestamp = DateTimeField(default=datetime.datetime.now)
    event_type = TextField()