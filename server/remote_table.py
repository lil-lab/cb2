from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from typing import List, Optional

import aiohttp

import schemas.clients
import schemas.mturk


# A table of active websocket connections. Maps from aiohttp.WebSocketResponse
# to Remote (defined below).
remote_table = {}

def AddRemote(web_socket_response, remote, assignment=None):
    remote_record, _ = (schemas.clients.Remote.get_or_create(hashed_ip=remote.hashed_ip, remote_port=remote.client_port))
    if assignment is not None:
        remote_record.worker = assignment.worker
        remote_record.assignment = assignment
    remote_record.save()
    remote_table[web_socket_response] = remote

def GetRemote(web_socket_response):
    return remote_table.get(web_socket_response, None)

def GetRemoteTable():
    return remote_table

def DeleteRemote(web_socket_response):
    del remote_table[web_socket_response]

def LogConnectionEvent(remote, event_str):
    event = schemas.clients.ConnectionEvents()
    remote = schemas.clients.Remote.get(schemas.clients.Remote.hashed_ip == remote.hashed_ip)
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

    def __str__(self):
        return f"m5sum hashed ip: {self.hashed_ip}, bytes (up/down): {self.bytes_up}/{self.bytes_down}, last message (up/down): {self.last_message_up}/{self.last_message_down}"