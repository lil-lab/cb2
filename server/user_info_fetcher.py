import hashlib
import logging

from aiohttp import web

from server.leaderboard import LookupUsernameFromMd5sum, UsernameFromHashedGoogleUserId
from server.messages.user_info import UserInfo, UserType

logger = logging.getLogger(__name__)


class UserInfoFetcher:
    def __init__(self):
        self._user_infos = {}  # ws: GoogleAuthConfirmation

    def fill_user_infos(self, ws: web.WebSocketResponse):
        if ws in self._user_infos:
            responses = self._user_infos[ws]
            del self._user_infos[ws]
            return responses
        return []

    async def handle_userinfo_request(self, ws: web.WebSocketResponse, remote) -> bool:
        """Given a userinfo request, fills in a userinfo response."""
        user_type = remote.user_type
        if user_type == UserType.NONE:
            user_name = ""
        elif user_type == UserType.GOOGLE:
            hashed_id = hashlib.sha256(remote.google_id.encode("utf-8")).hexdigest()
            user_name = UsernameFromHashedGoogleUserId(hashed_id)
            logger.info(f"RETURNING USERINFO FOR GOOGLE USER {user_name}")
        elif user_type == UserType.MTURK:
            # md5sum for mturkers.
            hashed_id = hashlib.md5(remote.mturk_id.encode("utf-8")).hexdigest()
            user_name = LookupUsernameFromMd5sum(hashed_id)
        else:
            user_name = ""
            logger.warn(f"Unknown user type {user_type}")
        logger.info(f"User info request for {user_name}")
        self._queue_userinfo(ws, UserInfo(user_name=user_name, user_type=user_type))

    def _queue_userinfo(self, ws, userinfo):
        if ws not in self._user_infos:
            self._user_infos[ws] = []
        self._user_infos[ws].append(userinfo)
