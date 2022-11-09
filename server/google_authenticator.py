import dataclasses
import logging

from aiohttp import web
from google.auth.transport import requests
from google.oauth2 import id_token

from server.config.config import GlobalConfig
from server.messages.google_auth import GoogleAuth, GoogleAuthConfirmation
from server.remote_table import GetRemote, SetRemote

logger = logging.getLogger(__name__)


class GoogleAuthenticator:
    def __init__(self):
        self._auth_confirmations = {}  # ws: GoogleAuthConfirmation

    def fill_auth_confirmations(self, ws: web.WebSocketResponse):
        if ws in self._auth_confirmations:
            responses = self._auth_confirmations[ws]
            del self._auth_confirmations[ws]
            return responses
        return []

    def handle_auth(self, ws: web.WebSocketResponse, auth: GoogleAuth) -> bool:
        """Verifies that the given Google auth token is valid."""
        config = GlobalConfig()
        try:
            idinfo = id_token.verify_oauth2_token(
                auth.token,
                requests.Request(),
                config.google_oauth_client_id,
            )
            if idinfo["iss"] not in [
                "accounts.google.com",
                "https://accounts.google.com",
            ]:
                raise ValueError("Wrong issuer.")
            # ID token is valid. Get the user's Google Account ID from the decoded token.
            remote = GetRemote(ws)
            remote = dataclasses.replace(
                remote, google_id=idinfo["sub"], google_auth_token=auth.token
            )
            SetRemote(ws, remote)
            self._queue_auth_success(ws)
        except ValueError:
            # Invalid token
            logger.info(f"Player {remote.player_id} has an invalid Google auth token.")
            self._queue_auth_failure(ws)

    def _queue_auth_success(self, ws):
        if ws not in self._auth_confirmations:
            self._auth_confirmations[ws] = []
        self._auth_confirmations[ws].append(GoogleAuthConfirmation(True))

    def _queue_auth_failure(self, ws):
        if ws not in self._auth_confirmations:
            self._auth_confirmations[ws] = []
        self._auth_confirmations[ws].append(GoogleAuthConfirmation(False))
