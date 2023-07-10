import logging
import random
from datetime import datetime
from typing import List

from cb2game.server.db_tools.db_utils import ListGames
from cb2game.server.messages import message_from_server, state_sync
from cb2game.server.messages.replay_messages import (
    Command,
    ReplayRequest,
    ReplayRequestType,
)
from cb2game.server.messages.rooms import Role
from cb2game.server.replay_state import ReplayState
from cb2game.server.schemas.game import Game

LEADER_MOVES_PER_TURN = 5
FOLLOWER_MOVES_PER_TURN = 10

LEADER_SECONDS_PER_TURN = 50
FOLLOWER_SECONDS_PER_TURN = 15

FOLLOWER_TURN_END_DELAY_SECONDS = 1

logger = logging.getLogger(__name__)


# The Cerealbar2 Demo State Machine. This is the state machine that is used to
# demo the game at conferences. Interesting games are loaded from the database
# and played back to the client. When a game finishes, the next one is started
# automatically. Long pauses between events are clipped to 2s.
#
# This class contains methods to consume and produce messages from/for the
# state machine. It consumes play/pause/rewind commands. It also contains a
# state machine update loop.  Produce messages and send them to the state
# machine with drain_messages().  Consume messages from the state machine with
# fill_messages().  You must call drain_messages() before each update() call and
# fill_messages() after each update() call.  It is recommended to use
# StateMachineDriver to run this class -- see server/state_machine_driver.py for
# details.
#
# In the process of renaming objective -> instruction. You may see the two terms
# used interchangeably here.
class DemoState(object):
    def __init__(
        self,
        room_id,
    ):
        self._games = DemoState.FetchDemoGames()
        logger.info(f"Number Demo games: {len(self._games)}")
        self._games_index = 0
        self._room_id = room_id
        self._done = False
        self._initialized = False
        self._player_ids = []
        self._start_time = datetime.utcnow()
        self._replay_ids = {}
        self._replay_state = None

    def StartNextGame(self):
        if len(self._games) == 0:
            return False
        game_id = self._games[self._games_index]
        game_record = Game.select().where(Game.id == game_id).get()
        self._replay_state = ReplayState(
            self._room_id, game_record, clip_long_events=True
        )
        # Register demo player IDs in replay_state.
        for player_id in self._player_ids:
            self._replay_ids[player_id] = self._replay_state.create_actor(player_id)
            logger.info(
                f"Mapped player_id: {player_id} to replay_id: {self._replay_ids[player_id]}"
            )
        # Trigger initialization.
        self._replay_state.Initialize()
        # Start the game.
        self._replay_state._command_queue.append(
            ReplayRequest(ReplayRequestType.REPLAY_COMMAND, command=Command.PLAY)
        )  # pylint: disable=protected-access
        self._games_index = (self._games_index + 1) % len(self._games)

    @staticmethod
    def FetchDemoGames():
        """A list of integer game IDs, sorted by score descending."""
        # ListGames returns a peewee query. Sort it by score descending. Then save the integer ids in self._games.
        game = ListGames()
        game = game.order_by(Game.score.desc())
        # Take the top N games.
        game = game.limit(50)
        # Print the highest and lowest scores.
        logger.info(f"Lowest score: {game[-1].score}")
        logger.info(f"Highest score: {game[0].score}")
        game_ids = [game.id for game in game]
        # Shuffle the games.
        random.shuffle(game_ids)
        return game_ids

    def has_pending_messages(self):
        if self._replay_state is not None:
            return False
        return self._replay_state.has_pending_messages()

    def end_game(self):
        if self._replay_state is not None:
            self._replay_state.end_game()

    def mark_player_disconnected(self, id):
        return None

    def map(self):
        return None

    def cards(self):
        return None

    def done(self):
        return len(self._games) == 0

    def player_ids(self):
        return self._player_ids

    def create_actor(self, role):
        # Replay actor. Just used to receive messages.
        actor_id = len(self._player_ids)
        if self._replay_state:
            self._replay_ids[actor_id] = self._replay_state.create_actor(actor_id)
        self._player_ids.append(actor_id)
        return actor_id

    def player_role(self, id):
        return Role.LEADER

    def start(self):
        if self._replay_state is not None:
            return self._replay_state.start()

    def update(self):
        if not self._initialized and len(self._player_ids):
            self.StartNextGame()
            self._initialized = True

        if self._replay_state is None:
            return

        if self._replay_state.out_of_events():
            self.StartNextGame()

        self._replay_state.update()

    def on_game_over(self):
        logger.info(f"Demo {self._room_id} is over.")

    def game_time(self):
        return datetime.utcnow() - self._start_time

    def turn_state(self):
        return Role.LEADER

    def calculate_score(self):
        return 0

    def selected_cards(self):
        return []

    def drain_messages(self, id, messages):
        if not self._replay_state:
            return
        replay_id = self._replay_ids.get(id, None)
        if replay_id is None:
            return False
        return self._replay_state.drain_messages(replay_id, messages)

    def free_actor(self, actor_id):
        if actor_id in self._player_ids:
            self._player_ids.remove(actor_id)
            self._replay_ids.pop(actor_id, None)

    def fill_messages(
        self, player_id, out_messages: List[message_from_server.MessageFromServer]
    ) -> bool:
        """Serializes all messages to one player into a linear history.

        If any messages have been generated this iteration, caps those
        messages with a StateMachineTick. This lets us separate logic
        iterations on the receive side.
        """
        if not self._replay_state:
            return None
        replay_id = self._replay_ids.get(player_id, None)
        if replay_id is None:
            return False
        result = self._replay_state.fill_messages(replay_id, out_messages)
        if result:
            # Override any TurnState messages to indicate that the game is not over.
            for message in out_messages:
                if message.type == message_from_server.MessageType.GAME_STATE:
                    message.turn_state.game_over = False
        return result

    # Returns the current state of the game for monitoring.
    def state(self, player_id=-1):
        return state_sync.StateSync(0, [], player_id, Role.LEADER)
