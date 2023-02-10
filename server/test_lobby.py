"""Unit tests for lobby code. """
import hashlib
import logging
import os
import unittest
import uuid
from datetime import datetime, timedelta

import time_machine

import server.messages.message_from_server as message_from_server
import server.messages.message_to_server as message_to_server
import server.schemas.mturk
from server.lobbies.follower_pilot_lobby import FollowerPilotLobby
from server.lobby_utils import LobbyInfo
from server.messages.rooms import (
    RoomManagementRequest,
    RoomRequestType,
    RoomResponseType,
)
from server.messages.user_info import UserType
from server.remote_table import AddRemote, Remote
from server.schemas.base import (
    ConnectDatabase,
    CreateTablesIfNotExists,
    SetDatabaseForTesting,
)
from server.schemas.defaults import ListDefaultTables
from server.schemas.mturk import WorkerQualLevel

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = ""  # Hide pygame welcome message

logger = logging.getLogger(__name__)

TEST_LOBBY_NAME = "test_lobby"
TEST_LOBBY_COMMENT = "test_lobby_comment"
TEST_TURK_SUBMIT_TO_URL = "http://0.0.0.0/"


class FollowerPilotLobbyTest(unittest.TestCase):
    """Test harness for FollowerPilotLoby."""

    def setUp(self):
        logging.basicConfig(level=logging.INFO)

        # In-memory db for test validation.
        SetDatabaseForTesting()
        ConnectDatabase()
        CreateTablesIfNotExists(ListDefaultTables())

        self.lobby = FollowerPilotLobby(
            LobbyInfo(TEST_LOBBY_NAME, TEST_LOBBY_COMMENT, 1)
        )

    # We use the below unique_*_id() functions as substitutes for the websocket
    # object in calls to the remote table. The remote table uses the websocket
    # object address as a unique identifier, without accessing any attributes or
    # methods. So plain strings should work too.
    def unique_bot_id(self):
        return f"BOT_{uuid.uuid4()}"

    def unique_worker_id(self):
        return f"MTURKER_{uuid.uuid4()}"

    # Not used as WebSocket replacement, but similar kind of test mock.
    def unique_assignment_id(self):
        return f"ASSIGNMENT_{uuid.uuid4()}"

    def unique_hit_id(self):
        return f"HIT_{uuid.uuid4()}"

    def register_bot(self, bot_id):
        remote = Remote("", 0, 0, 0, -1, -1, None, None, None, None, None, UserType.BOT)
        AddRemote(bot_id, remote)

    def register_mturk_leader(self, worker_id):
        self.register_mturker(worker_id, WorkerQualLevel.LEADER)

    def register_mturk_follower(self, worker_id):
        self.register_mturker(worker_id, WorkerQualLevel.FOLLOWER)

    def register_mturker(self, worker_id, qual_level):
        remote = Remote(
            "", 0, 0, 0, -1, -1, None, None, None, None, worker_id, UserType.MTURK
        )
        worker, _ = server.schemas.mturk.Worker.get_or_create(
            hashed_id=hashlib.md5(
                worker_id.encode("utf-8")
            ).hexdigest(),  # Worker ID is PII, so only save the hash.
            qual_level=qual_level,
        )
        assignment_id = self.unique_assignment_id()
        assignment, _ = server.schemas.mturk.Assignment.get_or_create(
            assignment_id=assignment_id,
            worker=worker,
            hit_id=self.unique_hit_id(),
            submit_to_url=TEST_TURK_SUBMIT_TO_URL,
        )
        AddRemote(worker_id, remote, assignment)

    def join_request(self):
        return message_to_server.MessageToServer(
            datetime.now(),
            message_to_server.MessageType.ROOM_MANAGEMENT,
            room_request=RoomManagementRequest(RoomRequestType.JOIN),
        )

    def register_and_join_leader(self):
        leader_id = self.unique_worker_id()
        self.register_mturk_leader(leader_id)
        self.lobby.handle_request(self.join_request(), leader_id)
        return leader_id

    def register_and_join_follower(self):
        follower_id = self.unique_worker_id()
        self.register_mturk_follower(follower_id)
        self.lobby.handle_request(self.join_request(), follower_id)
        return follower_id

    def register_and_join_bot(self):
        bot_id = self.unique_bot_id()
        self.register_bot(bot_id)
        self.lobby.handle_request(self.join_request(), bot_id)
        return bot_id

    def most_recent_lobby_message(self, user_id):
        messages = []
        last_message = self.lobby.drain_message(user_id)
        while last_message is not None:
            messages.append(last_message)
            last_message = self.lobby.drain_message(user_id)
        if len(messages) == 0:
            return None
        return messages[-1]

    def test_leader_mturker_id(self):
        leader_id = self.unique_worker_id()
        self.register_mturk_leader(leader_id)
        self.assertTrue(self.lobby.is_mturk_player(leader_id))

    def test_follower_mturker_id(self):
        follower_id = self.unique_worker_id()
        self.register_mturk_follower(follower_id)
        self.assertTrue(self.lobby.is_mturk_player(follower_id))

    def test_bot_id(self):
        bot_id = self.unique_bot_id()
        self.register_bot(bot_id)
        self.assertTrue(self.lobby.is_bot(bot_id))

    def test_human_leader_join(self):
        self.register_and_join_leader()
        self.assertEqual(len(self.lobby.leader_queue()), 1)

    def test_human_leaders_join(self):
        leader_ids = [self.register_and_join_leader() for i in range(10)]
        self.assertEqual(len(self.lobby.leader_queue()), len(leader_ids))

    def test_human_human_match(self):
        """Makes sure two humans match."""
        leader_id = self.register_and_join_leader()
        follower_id = self.register_and_join_follower()

        (leader, follower, _) = self.lobby.get_leader_follower_match()
        self.assertEqual(leader, leader_id)
        self.assertEqual(follower, follower_id)

    def test_human_bot_match(self):
        """Makes sure both humans and bots match."""
        with time_machine.travel(0, tick=False) as timer:
            leader_id = self.register_and_join_leader()
            follower_id = self.register_and_join_bot()

            # Immediately, no match is available. Returns pair of None.
            (leader, follower, _) = self.lobby.get_leader_follower_match()
            self.assertEqual(leader, None)
            self.assertEqual(follower, None)

            # After 10 seconds, the human is paired with the bot.
            timer.shift(10)

            (leader, follower, _) = self.lobby.get_leader_follower_match()
            self.assertEqual(leader, leader_id)
            self.assertEqual(follower, follower_id)

    def test_human_preference_match(self):
        """A human leader and two followers join. One follower is human. For the first 10 seconds, the human is preferred."""
        leader_id = self.register_and_join_leader()
        self.register_and_join_bot()
        follower_id = self.register_and_join_follower()

        # Immediately, the humans match.
        (leader, follower, _) = self.lobby.get_leader_follower_match()
        self.assertEqual(leader, leader_id)
        self.assertEqual(follower, follower_id)

    def test_delayed_human_preference_match(self):
        with time_machine.travel(0, tick=False) as timer:
            leader_id = self.register_and_join_leader()
            follower_bot_id = self.register_and_join_bot()
            self.register_and_join_follower()

            # After 10 seconds, the human is paired with the bot.
            timer.shift(10)

            (leader, follower, _) = self.lobby.get_leader_follower_match()
            self.assertEqual(leader, leader_id)
            self.assertEqual(follower, follower_bot_id)

    def test_leader_boot(self):
        with time_machine.travel(0, tick=False) as timer:
            leader_id = self.register_and_join_leader()

            # After 5m, the human is booted.
            timer.shift(timedelta(minutes=5, seconds=1))

            (leader, follower, _) = self.lobby.get_leader_follower_match()
            self.assertEqual(leader, None)
            self.assertEqual(follower, None)

            boot_message = self.most_recent_lobby_message(leader_id)
            self.assertIsNotNone(boot_message)
            self.assertEqual(
                boot_message.type, message_from_server.MessageType.ROOM_MANAGEMENT
            )
            self.assertEqual(
                boot_message.room_management_response.type,
                RoomResponseType.JOIN_RESPONSE,
            )
            self.assertTrue(
                boot_message.room_management_response.join_response.booted_from_queue
            )

    def test_follower_boot(self):
        with time_machine.travel(0, tick=False) as timer:
            follower_id = self.register_and_join_follower()

            # After 5m, the human is booted.
            timer.shift(timedelta(minutes=5, seconds=1))

            (leader, follower, _) = self.lobby.get_leader_follower_match()
            self.assertEqual(leader, None)
            self.assertEqual(follower, None)

            boot_message = self.most_recent_lobby_message(follower_id)
            self.assertIsNotNone(boot_message)
            self.assertEqual(
                boot_message.type, message_from_server.MessageType.ROOM_MANAGEMENT
            )
            self.assertEqual(
                boot_message.room_management_response.type,
                RoomResponseType.JOIN_RESPONSE,
            )
            self.assertTrue(
                boot_message.room_management_response.join_response.booted_from_queue
            )

    def test_human_preference_then_bot(self):
        """First, a human follower is preferred to a bot. Then, the remaining bot still matches with a human leader."""
        with time_machine.travel(0, tick=False) as timer:
            leaders = [self.register_and_join_leader() for i in range(3)]
            bot_id = self.register_and_join_bot()
            follower_before = self.register_and_join_follower()

            (leader, follower, _) = self.lobby.get_leader_follower_match()
            self.assertEqual(leader, leaders[0])
            self.assertEqual(follower, follower_before)

            timer.shift(10)

            follower_after = self.register_and_join_follower()

            (leader, follower, _) = self.lobby.get_leader_follower_match()
            self.assertEqual(leader, leaders[1])
            self.assertEqual(follower, bot_id)

            (leader, follower, _) = self.lobby.get_leader_follower_match()
            self.assertEqual(leader, leaders[2])
            self.assertEqual(follower, follower_after)

    def test_bot_priority_after_5m(self):
        """A set of human followers is preferred to a bot follower. 10s later, the bot is preferred to a human."""
        with time_machine.travel(0, tick=False) as timer:
            leaders = [self.register_and_join_leader() for i in range(12)]
            bot_id = self.register_and_join_bot()
            followers_before = [self.register_and_join_follower() for i in range(10)]

            for i in range(10):
                (leader, follower, _) = self.lobby.get_leader_follower_match()
                self.assertEqual(leader, leaders[i])
                self.assertEqual(follower, followers_before[i])

            timer.shift(10)

            follower_after = self.register_and_join_follower()

            (leader, follower, _) = self.lobby.get_leader_follower_match()
            self.assertEqual(leader, leaders[10])
            self.assertEqual(follower, bot_id)

            (leader, follower, _) = self.lobby.get_leader_follower_match()
            self.assertEqual(leader, leaders[11])
            self.assertEqual(follower, follower_after)
