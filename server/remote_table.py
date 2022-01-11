from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config, LetterCase
from datetime import datetime
from marshmallow import fields
from typing import List, Optional

import aiohttp

# A table of active websocket connections. Maps from aiohttp.WebSocketResponse
# to Remote (defined below).
remote_table = {}

def AddRemote(web_socket_response, remote):
    remote_table[web_socket_response] = remote

def GetRemote(web_socket_response):
    return remote_table.get(web_socket_response, None)

def GetRemoteTable():
    return remote_table

def DeleteRemote(web_socket_response):
    del remote_table[web_socket_response]

@dataclass_json
@dataclass
class Remote:
    ip: str
    bytes_down: int
    bytes_up: int
    last_message_down: float
    last_message_up: float
    request: aiohttp.web.BaseRequest
    response: aiohttp.web.WebSocketResponse