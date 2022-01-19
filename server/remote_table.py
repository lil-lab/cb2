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
class Worker:
    hashed_id: str

    def __str__(self):
        return f"hashed_id: {self.hashed_id}"

PREVIEW_ASSIGNMENT_ID = "ASSIGNMENT_ID_NOT_AVAILABLE"

@dataclass_json
@dataclass
class Assignment:
    assignment_id: str
    hit_id: str
    worker: Worker
    submit_to_url: str

    def is_preview(self):
        return self.assignment_id == PREVIEW_ASSIGNMENT_ID
    
    def __str__(self):
        return f"assignment: {self.assignment_id}, hit: {self.hit_id}, submit_to_url: {self.submit_to_url}, worker: {{{self.worker}}}"

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
    mturk_assignment: Assignment


    def __str__(self):
        return f"ip: {self.ip}, bytes (up/down): {self.bytes_up}/{self.bytes_down}, last message (up/down): {self.last_message_up}/{self.last_message_down}, mturk_assignment: {self.mturk_assignment}"