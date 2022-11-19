import asyncio
import dataclasses
import functools
import hashlib
import logging

from aiohttp import web
from google.auth.transport import requests
from google.oauth2 import id_token

import server.schemas.google_user
from server.config.config import GlobalConfig
from server.leaderboard import SetDefaultGoogleUsername, UsernameFromHashedGoogleUserId
from server.messages.google_auth import GoogleAuth, GoogleAuthConfirmation
from server.messages.user_info import UserType
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

    async def handle_auth(self, ws: web.WebSocketResponse, auth: GoogleAuth) -> bool:
        """Verifies that the given Google auth token is valid."""
        config = GlobalConfig()
        logger.info(f"Verifying Google auth token: {auth.token}")
        try:
            request = requests.Request()
            request_with_timeout = functools.partial(request, timeout=2)
            # Run the following in a separate executor.
            idinfo = await asyncio.to_thread(
                lambda: id_token.verify_oauth2_token(
                    auth.token,
                    request_with_timeout,
                    config.google_oauth_client_id,
                )
            )
            if idinfo["iss"] not in [
                "accounts.google.com",
                "https://accounts.google.com",
            ]:
                raise ValueError("Wrong issuer.")
            # ID token is valid. Get the user's Google Account ID from the decoded token.
            remote = GetRemote(ws)
            remote = dataclasses.replace(
                remote,
                google_id=idinfo["sub"],
                google_auth_token=auth.token,
                user_type=UserType.GOOGLE,
            )
            SetRemote(ws, remote)
            logger.info(f"Google auth success for {idinfo['sub']}")
            self._queue_auth_success(ws)
            # Register the user in the database if they don't exist.
            hashed_user_id = hashlib.sha256(idinfo["sub"].encode("utf-8")).hexdigest()
            google_user = server.schemas.google_user.GoogleUser.get_or_create(
                hashed_google_id=hashed_user_id,
                qual_level=0,  # Unused for now.
                experience=None,
                kv_store="{}",
            )
            if UsernameFromHashedGoogleUserId(hashed_user_id) is None:
                SetDefaultGoogleUsername(hashed_user_id)
        except ValueError:
            # Invalid token
            logger.info(f"Player has an invalid Google auth token.")
            self._queue_auth_failure(ws)

    def _queue_auth_success(self, ws):
        if ws not in self._auth_confirmations:
            self._auth_confirmations[ws] = []
        self._auth_confirmations[ws].append(GoogleAuthConfirmation(True))

    def _queue_auth_failure(self, ws):
        if ws not in self._auth_confirmations:
            self._auth_confirmations[ws] = []
        self._auth_confirmations[ws].append(GoogleAuthConfirmation(False))
