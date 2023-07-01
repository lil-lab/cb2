import uuid
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp
import dateutil
from dataclasses_json import config, dataclass_json
from marshmallow import fields

import cb2game.server.schemas.clients as clients_db
from cb2game.server.messages.user_info import UserType

# A table of active websocket connections. Maps from aiohttp.WebSocketResponse
# to Remote (defined below).
remote_table = {}

remote_worker_table = {}


def AddRemote(web_socket_response, remote, assignment=None):
    remote_record, _ = clients_db.Remote.get_or_create(
        hashed_ip=remote.hashed_ip, remote_port=remote.client_port
    )
    if assignment is not None:
        remote_record.worker = assignment.worker
        remote_record.assignment = assignment
        remote_worker_table[web_socket_response] = assignment.worker
    remote_record.save()
    remote.uuid = uuid.uuid4()
    remote_table[web_socket_response] = remote


def GetWorkerFromRemote(web_socket_response):
    return remote_worker_table.get(web_socket_response, None)


def GetRemote(web_socket_response):
    return remote_table.get(web_socket_response, None)


def SetRemote(web_socket_response, remote):
    remote_table[web_socket_response] = remote


def GetRemoteTable():
    return remote_table


def DeleteRemote(web_socket_response):
    del remote_table[web_socket_response]


def LogConnectionEvent(remote, event_str):
    event = clients_db.ConnectionEvents()
    remote = clients_db.Remote.get(clients_db.Remote.hashed_ip == remote.hashed_ip)
    event.remote = remote
    event.event_type = event_str
    event.save()


@dataclass_json
@dataclass
class Remote:
    hashed_ip: str
    client_port: int
    bytes_down: int
    bytes_up: int
    last_message_down: float
    last_message_up: float
    request: aiohttp.web.BaseRequest
    response: aiohttp.web.WebSocketResponse
    # A JWT encoded Google sso token https://www.rfc-editor.org/rfc/rfc7519
    google_auth_token: str = None
    google_id: str = None
    mturk_id: str = None
    user_type: UserType = UserType.NONE
    last_ping: datetime = field(
        metadata=config(
            encoder=datetime.isoformat,
            decoder=dateutil.parser.isoparse,
            mm_field=fields.DateTime(format="iso"),
        ),
        default=datetime.min,
    )
    time_offset: float = 0.0
    latency: float = 0.0
    uuid: str = ""

    def __str__(self):
        return f"m5sum hashed ip: {self.hashed_ip}, bytes (up/down): {self.bytes_up}/{self.bytes_down}, last message (up/down): {self.last_message_up}/{self.last_message_down}, time_offset: {self.time_offset}, latency: {self.latency}"
