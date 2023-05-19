""" This table captures bugreports from the client.

    To see the structure of the serialized bugreport, see
    server/messages/bug_report.py.
"""
import datetime
import uuid

from peewee import DateTimeField, TextField, UUIDField

from server.schemas.base import BaseModel


class ClientException(BaseModel):
    """When a client sends a bug report, we store it in this table.

    Depending on config, there's a maximum number of bugs we store before
    old ones are deleted.
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4, unique=True)
    game_id = TextField()
    role = TextField()
    date = DateTimeField(default=datetime.datetime.now)
    bug_report = TextField()
    """Serialized JSON of BugReport from server/messages/bug_report.py"""
    condition = TextField()
    """The exception encountered. """
    stack_trace = TextField()
    """The stack trace of the exception. """
