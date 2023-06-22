import dataclasses
import logging
import math
import queue
import uuid
from collections import deque
from datetime import datetime, timedelta
from queue import Queue
from typing import List

import humanhash

import server.config.config as config
import server.google_experience as google_experience
import server.leaderboard as leaderboard
import server.map_utils as map_utils
import server.mturk_experience as mturk_experience
import server.scenario_util as scenario_util
from server.actor import Actor
from server.assets import AssetId
from server.card import Card, CardSelectAction, SetCompletionActions
from server.game_recorder import GameRecorder
from server.hex import HecsCoord
from server.map_provider import CachedMapRetrieval, MapProvider, MapType
from server.messages import (
    live_feedback,
    message_from_server,
    message_to_server,
    state_sync,
)
from server.messages.action import ActionType, Color
from server.messages.feedback_questions import FeedbackResponse
from server.messages.prop import PropUpdate
from server.messages.rooms import Role
from server.messages.scenario import Scenario, ScenarioResponse, ScenarioResponseType
from server.messages.sound_trigger import SoundClipType, SoundTrigger
from server.messages.state_sync import StateMachineTick
from server.messages.turn_state import GameOverMessage, TurnUpdate
from server.state_utils import (
    FOLLOWER_FEEDBACK_QUESTIONS,
    FOLLOWER_MOVES_PER_TURN,
    FOLLOWER_SECONDS_PER_TURN,
    FOLLOWER_TURN_END_DELAY_SECONDS,
    LEADER_MOVES_PER_TURN,
    LEADER_SECONDS_PER_TURN,
    turn_reward,
)
from server.username_word_list import USERNAME_WORDLIST
from server.util import CountDownTimer, JsonSerialize

logger = logging.getLogger(__name__)


# The Cerealbar2 State Machine. This is the state machine that is used to drive the game.
# This class contains methods to consume and produce messages from/for the state machine. It also contains a state machine update loop.
# Produce messages and send them to the state machine with drain_messages().
# Consume messages from the state machine with fill_messages().
# You must call drain_messages() before each update() call and fill_messages() after each update() call.
# It is recommended to use StateMachineDriver to run this class -- see server/state_machine_driver.py for details.
#
# In the process of renaming objective -> instruction. You may see the two terms used interchangeably here.
class State(object):
    @classmethod
    def InitializeFromExistingState(
        cls,
        room_id,
        event_uuid: str = "",
        realtime_actions: bool = False,
        lobby: "server.Lobby" = None,
        log_to_db: bool = False,
    ):
        """Initialize the game from a given event.

        This is used by the pyclient to launch a reconstructed game (training)
        from a given event UUID in the database. This is used locally for
        training. See py_client/local_game_coordinator.py for usage.

        Returns: (state_machine: State, failure_reason: str = "")

        If return value state_machine is none, the reason for failure is in failure_reason.
        """
        scenario, err = scenario_util.ReconstructScenarioFromEvent(event_uuid)
        assert scenario is not None, f"Failed to reconstruct scenario: {err}"
        s = State(
            room_id,
            None,
            True,
            scenario,
            realtime_actions=realtime_actions,
            log_to_db=log_to_db,
            lobby=lobby,
        )
        return s, ""

    def __init__(
        self,
        room_id,
        game_record,
        use_preset_data: bool = False,
        scenario: Scenario = None,
        log_to_db: bool = True,
        realtime_actions: bool = False,
        lobby: "server.Lobby" = None,
    ):
        """Initialize the game state.

        Note that if you initialize this class, it will NOT contain actors until you call create_actor().
        The actor state information is stored in _preloaded_actors.

        Args:
            room_id (str): Room id for this game. Unique string used in status page.
            game_record (GameRecorder): Object to record game events to the database.
            use_preset_data (bool): If true, init from provided preset data.
            scenario (Scenario): Preset data. See server/messages/scenario.py.
            log_to_db (bool): If true, log game events to the database.
            realtime_actions (bool): Enables realtime actions. See server/actor.py.
        """
        self._start_time = datetime.utcnow()
        self._room_id = room_id
        self._lobby = lobby

        # Rolling count of iteration loop. Used to indicate when an iteration of
        # the logic loop has occurred. Sent out in StateMachineTick messages
        # (only if an event occurred that loop).
        self._iter = 0

        self._initialized = False

        # Maps from actor_id (prop id) to actor object (see definition below).
        self._actors = {}
        self._leader = None
        self._follower = None
        self._role_history = (
            {}
        )  # Map from actor_id to role. Preserved after free_actor().
        # True if a player was added since the last iteration.
        self._actors_added = False
        self._realtime_actions = realtime_actions

        self._turn_complete_queue = deque()

        self._instructions = deque()  # A list of unprocessed instructions.
        self._instruction_history = (
            deque()
        )  # All instructions, including completed/cancelled ones.
        self._instructions_stale = (
            {}
        )  # Maps from player_id -> bool if their objective list is stale.
        self._instruction_added = (
            False  # True if an instruction was added since the last iteration.
        )
        self._instruction_complete_queue = deque()
        self._live_feedback_queue = deque()

        self._map_stale = {}  # Maps from player_id -> bool if their map is stale.
        self._map_update_count = 0

        self._prop_stale = (
            {}
        )  # Maps from player_id -> bool if their prop list is stale.

        self._sound_trigger_messages = (
            {}
        )  # Maps from player_id -> List[sound trigger messages].

        self._ticks = {}  # Maps from player_id -> tick message.

        self._synced = {}
        self._action_history = {}
        self._turn_history = {}

        self._scenario_download_pending = (
            {}
        )  # Maps from player_id -> bool if they requested a scenario download
        self._scenario_download = {}  # Maps from player_id -> Scenario

        self._preloaded_actors = {}

        self._last_card_step_actor = None

        self._turn_state = None

        # We need to add a delay to the end of the follower's turn. So instead of ending the
        # turn immediately, we start the follower turn delay timer. When the timer reachers
        self._follower_turn_end_timer = CountDownTimer(
            duration_s=FOLLOWER_TURN_END_DELAY_SECONDS
        )
        self._follower_turn_end_reason = ""

        if use_preset_data:
            self._game_recorder = GameRecorder(None, disabled=True)
            # Delayed means that the actor state will be loaded when players join.
            self._set_scenario(scenario, realtime_actions, delayed_actor_load=True)
        else:
            # Records everything that happens in a game.
            self._game_recorder = (
                GameRecorder(game_record)
                if log_to_db
                else GameRecorder(None, disabled=True)
            )
            # Map props and actors share IDs from the same pool, so the ID assigner
            # is shared to prevent overlap.
            self._map_provider = CachedMapRetrieval()
            initial_turn = TurnUpdate(
                Role.LEADER,
                LEADER_MOVES_PER_TURN,
                6,
                datetime.utcnow() + State.turn_duration(Role.LEADER),
                datetime.utcnow(),
                0,
                0,
                0,
            )
            self._send_turn_state(initial_turn)

        self._map_update = self._map_provider.map()
        # Maps from player_id -> list of props to update.
        self._prop_update = self._map_provider.prop_update()

        # Maps from player_id -> live_feedback.FeedbackType if live feedback is
        # pending. Otherwise live_feedback.FeedbackType.None.
        self._live_feedback = {}

        self._done = False

        self._current_set_invalid = self._map_provider.selected_cards_collide()
        # Adds card covers.
        self._prop_update = map_utils.CensorCards(self._prop_update, None)

        # Maps from player_id -> list of feedback questions (for transmission).
        self._feedback_questions = {}
        # Maps from player_id -> list of feedback questions that have not been answered.
        self._unanswered_feedback_question = {}

    def game_time(self):
        """Return timedelta between now and when the game started."""
        return datetime.utcnow() - self._start_time

    @staticmethod
    def turn_duration(role):
        return (
            timedelta(seconds=LEADER_SECONDS_PER_TURN)
            if role == Role.LEADER
            else timedelta(seconds=FOLLOWER_SECONDS_PER_TURN)
        )

    def end_game(self):
        logger.debug("Game ending.")
        self._done = True

    def _announce_action(self, action):
        # Marks an action as validated (i.e. it did not conflict with other actions).
        # Queues this action to be sent to each user.
        for id in self._actors:
            actor = self._actors[id]
            self._action_history[actor.actor_id()].append(action)

    def mark_player_disconnected(self, id):
        if id not in self._role_history:
            logger.warning(f"Player {id} not found in game.")
            return
        role = self._role_history[id]
        kvals = self._game_recorder.kvals()
        if "disconnected" in kvals:
            logger.warning(f"Player {kvals['disconnected']} already disconnected.")
            kvals["disconnected"].append(role.name)
        kvals["disconnected"] = [role.name]
        logging.info(f"Setting kvals: {kvals}")
        self._game_recorder.set_kvals(kvals)

    def map(self):
        return self._map_provider.map()

    def cards(self):
        return self._map_provider.cards()

    def done(self):
        return self._done

    def player_ids(self):
        return self._actors.keys()

    def player_role(self, id):
        return self._actors[id].role()

    def start(self):
        self._start_time = datetime.utcnow()

    def _self_initialize(self):
        """This exists for scenario_state and other "private" clients to skip the player join initializing process."""
        logger.debug(
            f"Initializing game with leader {self._leader} and follower {self._follower}"
        )
        self._game_recorder.record_initial_state(
            self._iter,
            self._map_provider.map(),
            self._map_provider.prop_update(),
            self._turn_state,
            self._leader,
            self._follower,
        )
        self._game_recorder.record_start_of_turn(self._turn_state, "StartOfGame")
        self._initialized = True
        logger.debug(f"Game initialized.")

    def update(self):
        send_tick = False

        if not self._initialized:
            if self._leader is not None and self._follower is not None:
                self._game_recorder.record_initial_state(
                    self._iter,
                    self._map_provider.map(),
                    self._map_provider.prop_update(),
                    self._turn_state,
                    self._leader,
                    self._follower,
                )
                self._game_recorder.record_start_of_turn(
                    self._turn_state, "StartOfGame"
                )
                self._initialized = True
            else:
                logger.debug(f"Waiting for players to join. Not Initialized.")
                return

        # Have we received an instruction since the last iteration?
        if self._instruction_added:
            self._instruction_added = False
            logger.debug(f"New instruction added.")
            send_tick = True

        if self._actors_added:
            self._actors_added = False
            logger.debug(f"New actors added.")
            send_tick = True

        if datetime.utcnow() >= self._turn_state.turn_end:
            self._update_turn(end_reason="RanOutOfTime")
            logger.debug(f"Turn timed out.")
            send_tick = True

        # Handle actor actions.
        for actor_id in self._actors:
            actor = self._actors[actor_id]
            while actor.has_actions():
                proposed_action = actor.peek()
                if not self._turn_state.turn == actor.role():
                    actor.drop()
                    self.desync(actor_id)
                    logger.debug(
                        f"Actor {actor_id} is not the current role. Dropping pending action."
                    )
                    logger.debug(f"action out of turn tick.")
                    send_tick = True
                    continue
                if self._turn_state.moves_remaining == 0:
                    actor.drop()
                    self.desync(actor_id)
                    logger.debug(
                        f"Actor {actor_id} is out of moves. Dropping pending action."
                    )
                    logger.debug(f"actor out of moves but sent action tick.")
                    send_tick = True
                    continue

                if not self._valid_action(actor_id, proposed_action):
                    actor.drop()
                    self.desync(actor_id)
                    logger.debug(f"actor invalid action tick.")
                    send_tick = True
                    continue

                if (
                    (not self._realtime_actions)
                    or (not actor.is_realtime)
                    or actor.peek_action_done()
                ):
                    position_before = actor.location()
                    heading_before = actor.heading_degrees()
                    actor.step()
                    active_instruction = None
                    if (actor.role() == Role.FOLLOWER) and (
                        len(self._instructions) > 0
                    ):
                        active_instruction = self._instructions[0]
                    self._game_recorder.record_move(
                        actor,
                        proposed_action,
                        active_instruction,
                        position_before,
                        heading_before,
                    )
                    self._announce_action(proposed_action)
                    color = (
                        Color(0, 0, 1, 1)
                        if not self._current_set_invalid
                        else Color(1, 0, 0, 1)
                    )
                    self._check_for_stepped_on_cards(actor_id, proposed_action, color)
                    self._update_turn()
                    logger.debug(f"Action occurred tick.")
                    send_tick = True

        if (
            self._turn_state.turn == Role.FOLLOWER
            and self._turn_state.moves_remaining <= 0
        ):
            if self._realtime_actions:
                # Start end-turn timer.
                self._follower_turn_end_reason = "FollowerOutOfMoves"
                self._follower_turn_end_timer.start()
            else:
                self._update_turn(
                    force_role_switch=True, end_reason="FollowerOutOfMoves"
                )
                logger.debug(f"follower out of moves tick.")
                send_tick = True

        while len(self._turn_complete_queue) > 0:
            (id, reason) = self._turn_complete_queue.popleft()
            if id not in self._actors:
                continue
            actor = self._actors[id]
            if actor.role() == self._turn_state.turn:
                self._update_turn(force_role_switch=True, end_reason=reason)
                logger.debug(f"turn ended tick.")
                send_tick = True
                continue
            # The leader can end the follower's turn via an interruption
            if actor.role() == Role.LEADER and reason == "UserPromptedInterruption":
                self._cancel_pending_instructions()
                self._update_turn(force_role_switch=True, end_reason=reason)
                logger.debug(f"interruption tick.")
                send_tick = True
                continue

        while len(self._instruction_complete_queue) > 0:
            (id, objective_complete) = self._instruction_complete_queue.popleft()
            self._handle_instruction_complete(id, objective_complete)
            logger.debug(f"instruction complete tick.")
            send_tick = True

        while len(self._live_feedback_queue) > 0:
            (id, feedback) = self._live_feedback_queue.popleft()
            for actor_id in self._actors:
                self._live_feedback[actor_id] = feedback.signal
            send_tick = True
            active_instruction = None
            if len(self._instructions) > 0:
                active_instruction = self._instructions[0]
                if feedback.signal == live_feedback.FeedbackType.POSITIVE:
                    active_instruction.pos_feedback += 1
                elif feedback.signal == live_feedback.FeedbackType.NEGATIVE:
                    active_instruction.neg_feedback += 1
                active_instruction.update_feedback_text()
            self._game_recorder.record_live_feedback(
                feedback, self._follower, active_instruction
            )

        # If the follower currently has no instructions, end their turn.
        if self._turn_state.turn == Role.FOLLOWER and not self._has_instructions_todo():
            if self._realtime_actions:
                # Start end-turn timer.
                self._follower_turn_end_reason = "FollowerFinishedInstructions"
                self._follower_turn_end_timer.start()
                new_turn_state = dataclasses.replace(
                    self._turn_state, moves_remaining=0
                )
                self._send_turn_state(new_turn_state)
            else:
                self._update_turn(
                    force_role_switch=True, end_reason="FollowerFinishedInstructions"
                )
                logger.debug(f"No realtime actions follower turn ended.")
                send_tick = True

        if self._realtime_actions and self._follower_turn_end_timer.expired():
            self._follower_turn_end_timer.clear()
            self._update_turn(
                force_role_switch=True, end_reason=self._follower_turn_end_reason
            )
            logger.debug(
                f"Follower Turn Ended. Reason: {self._follower_turn_end_reason}"
            )
            self._follower_turn_end_reason = ""
            send_tick = True

        selected_cards = list(self._map_provider.selected_cards())
        cards_changed = False
        if (
            self._map_provider.selected_cards_collide()
            and not self._current_set_invalid
        ):
            self._current_set_invalid = True
            cards_changed = True
            # Indicate invalid set.
            for card in selected_cards:
                # Outline the cards in red.
                card_select_action = CardSelectAction(card.id, True, Color(1, 0, 0, 1))
                self._map_provider.set_color(card.id, Color(1, 0, 0, 1))
                self._announce_action(card_select_action)
                # Find the actor that selected this card.
                stepping_actor = None
                for actor_id in self._actors:
                    if self._actors[actor_id].location() == card.location:
                        stepping_actor = self._actors[actor_id]
                        break
                self._game_recorder.record_card_selection(stepping_actor, card)
            self.queue_leader_sound(SoundClipType.INVALID_SET)
            self.queue_follower_sound(SoundClipType.INVALID_SET)

        if (
            not self._map_provider.selected_cards_collide()
            and self._current_set_invalid
        ):
            logger.debug(
                "Marking set as clear (not invalid) because it is smaller than 3."
            )
            self._current_set_invalid = False
            cards_changed = True
            for card in selected_cards:
                # Outline the cards in blue.
                card_select_action = CardSelectAction(card.id, True, Color(0, 0, 1, 1))
                self._map_provider.set_color(card.id, Color(0, 0, 1, 1))
                self._announce_action(card_select_action)

        if self._map_provider.selected_valid_set():
            self._current_set_invalid = False
            added_turns = 0
            cards_changed = True

            sound_clip_type = SoundClipType.VALID_SET
            # If the score is 5, 10, 15, or 20, play a different easter egg sound.
            if self._turn_state.score == 4:
                sound_clip_type = SoundClipType.EASTER_EGG_SOUND_1
            elif self._turn_state.score == 9:
                sound_clip_type = SoundClipType.EASTER_EGG_SOUND_2
            elif self._turn_state.score == 14:
                sound_clip_type = SoundClipType.EASTER_EGG_SOUND_3
            elif self._turn_state.score == 19:
                sound_clip_type = SoundClipType.EASTER_EGG_SOUND_4
            self.queue_leader_sound(sound_clip_type)
            self.queue_follower_sound(sound_clip_type)

            added_turns = turn_reward(self._turn_state.sets_collected)
            new_turn_state = TurnUpdate(
                self._turn_state.turn,
                self._turn_state.moves_remaining,
                self._turn_state.turns_left + added_turns,
                self._turn_state.turn_end,
                self._turn_state.game_start,
                self._turn_state.sets_collected + 1,
                self._turn_state.score + 1,
                self._turn_state.turn_number,
            )
            self._send_turn_state(new_turn_state)
            self._game_recorder.record_card_set(
                self._last_card_step_actor, selected_cards, self._turn_state.score
            )
            self._game_recorder.record_turn_state(new_turn_state, "ScoredSet")
            # Add 3 new cards before clearing selected cards. This prevents
            # us from accidentally spawning cards in the same location as
            # the previous 3, which is confusing to the user.
            new_cards = self._map_provider.add_random_unique_set()
            for card in new_cards:
                self._game_recorder.record_card_spawn(card)
            # Clear card state and remove the cards in the winning set.
            logger.debug("Clearing selected cards")
            for card in selected_cards:
                self._map_provider.set_selected(card.id, False)
                actions = SetCompletionActions(card.id)
                for action in actions:
                    self._announce_action(action)
                    self._game_recorder.record_action(
                        action, "select", card.location, card.rotation_degrees
                    )
                self._map_provider.remove_card(card.id)

        if cards_changed:
            # We've changed cards, so we need to mark the map as stale for all players.
            self._prop_update = self._map_provider.prop_update()
            self._prop_update = map_utils.CensorCards(self._prop_update, None)
            self._send_state_machine_info = True
            for actor_id in self._actors:
                self._prop_stale[actor_id] = True

        # Check to see if the game is over.
        if self._turn_state.turns_left <= -1:
            logger.debug(f"Game {self._room_id} is out of turns. Game over!")
            game_over_message = GameOverMessage(
                self._turn_state.game_start,
                self._turn_state.sets_collected,
                self._turn_state.score,
                self._turn_state.turn_number,
            )
            self._send_turn_state(game_over_message)
            self.end_game()
            return

        # If any player requested a scenario download, queue it.
        for actor_id in self._actors:
            if actor_id not in self._scenario_download_pending:
                self._scenario_download_pending[actor_id] = False
            if self._scenario_download_pending[actor_id]:
                self._scenario_download_pending[actor_id] = False
                hasher = humanhash.HumanHasher(wordlist=USERNAME_WORDLIST)
                unique_id = str(uuid.uuid4().hex)
                scenario_id = hasher.humanize(unique_id, words=2)
                scenario_obj = self._get_scenario(actor_id, scenario_id)
                # Give the scenario a unique ID.
                self._scenario_download[actor_id] = JsonSerialize(scenario_obj)

        # If any state transitions occurred which prompt a tick, send one.
        if send_tick:
            self._iter = (self._iter + 1) % 2**32
            self._game_recorder.record_tick(self._iter)
            logger.debug(
                f"============================================== Sending tick {self._iter}"
            )
            tick_message = StateMachineTick(iter=self._iter)
            for id in self._actors:
                self._ticks[id] = tick_message

    def tick_count(self):
        """State machine event tick count.

        The state machine keeps a counter which gets incremented whenever an
        in-game event occurs. Events which are casually linked (E.x.  a card is
        selected, completing a set, which causes the score to increase) should
        occur in the same tick. This can be used as a time-independent and
        deterministic (almost) ordering of events in the game.

        Limits to determinism:
        If some events happen during the same state machine poll period, they
        will get put into the same tick. The poll period is roughly 2ms (though
        you should measure this directly, as it will change depending on server
        resources availability and CB2 software version). Since arrival time of
        events depends on the timing of external factors (network messages,
        etc), it results in slightly
        nondeterministic behavior.  For example, an actor joining usually gets
        its own tick, but if two actors join simultaneously (within ~2ms) they
        will both happen on the same tick. This means that the tick count can't
        always be relied upon to be deterministically the same, given the same
        events occurring (unless those events themselves are deterministic, like
        in unit tests or local self play with non-random agents).
        """
        return self._iter

    def scenario_id() -> str:
        """Boilerplate. Only implemented in scenario_state.py."""
        return ""

    def on_game_over(self):
        logger.debug(f"Game {self._room_id} is over.")
        self._game_recorder.record_game_over()
        if self._game_recorder.record() is not None:
            leaderboard.UpdateLeaderboard(self._game_recorder.record())
            mturk_experience.UpdateWorkerExperienceTable(self._game_recorder.record())
            google_experience.UpdateGoogleUserExperienceTable(
                self._game_recorder.record()
            )

    def _has_instructions_todo(self):
        for instruction in self._instructions:
            if not instruction.completed and not instruction.cancelled:
                return True
        return False

    def _update_turn(self, force_role_switch=False, end_reason=""):
        if self._turn_state.turn == Role.PAUSED:
            return
        opposite_role = (
            Role.LEADER if self._turn_state.turn == Role.FOLLOWER else Role.FOLLOWER
        )
        role_switch = (
            datetime.utcnow() >= self._turn_state.turn_end
        ) or force_role_switch
        next_role = self._turn_state.turn
        if role_switch:
            if (
                self._turn_state.turn == Role.FOLLOWER
            ) and self._lobby.lobby_info().follower_feedback_questions:
                next_role = Role.QUESTIONING_FOLLOWER
                # Queue up the feedback questions for the follower.
                for question in FOLLOWER_FEEDBACK_QUESTIONS:
                    question.uuid = uuid.uuid4()
                    question.transmit_time_s = (
                        datetime.utcnow() - self._turn_state.game_start
                    ).total_seconds()
                    self._feedback_questions[self._follower.actor_id()].append(question)
                    self._unanswered_feedback_question[
                        self._follower.actor_id()
                    ].append(question)
                    self._game_recorder.record_feedback_question(question)
            else:
                next_role = opposite_role
        if self._turn_state.turn == Role.QUESTIONING_FOLLOWER:
            # If there are no pending questions, switch to the leader role.
            if len(self._unanswered_feedback_question[self._follower.actor_id()]) == 0:
                self._turn_state.turn = Role.LEADER
        # Force the leader to act if there's no uncompleted instructions.
        turn_skipped = False
        if next_role == Role.FOLLOWER and not self._has_instructions_todo():
            next_role = Role.LEADER
            turn_skipped = True
        moves_remaining = max(self._turn_state.moves_remaining - 1, 0)
        previous_moves_remaining = moves_remaining
        turns_left = self._turn_state.turns_left
        turn_end = self._turn_state.turn_end
        turn_number = self._turn_state.turn_number
        end_of_turn = False
        if role_switch:
            # This is a mitigation to the invisible cards glitch. Update cards on role switches.
            self._prop_update = self._map_provider.prop_update()
            for actor_id in self._actors:
                self._prop_stale[actor_id] = True
            self._prop_update = map_utils.CensorCards(self._prop_update, None)
            end_of_turn = next_role == Role.LEADER
            moves_remaining = self._moves_per_turn(next_role)
            turn_end = datetime.utcnow() + State.turn_duration(next_role)
            if end_of_turn:
                turns_left -= 1
                turn_number += 1

        turn_update = TurnUpdate(
            next_role,
            moves_remaining,
            turns_left,
            turn_end,
            self._turn_state.game_start,
            self._turn_state.sets_collected,
            self._turn_state.score,
            turn_number,
        )
        self._send_turn_state(turn_update)

        if end_of_turn:
            self._game_recorder.record_start_of_turn(
                self._turn_state,
                end_reason,
                turn_skipped,
                previous_moves_remaining == 0,
                len(self._instructions) == 0,
            )
        elif role_switch:
            # Record a copy of the current turn state.
            self._game_recorder.record_turn_state(self._turn_state, "RoleSwitch")

    def _moves_per_turn(self, role):
        return LEADER_MOVES_PER_TURN if role == Role.LEADER else FOLLOWER_MOVES_PER_TURN

    def turn_state(self):
        return self._turn_state

    def calculate_score(self):
        self._turn_state.score = self._turn_state.sets_collected * 100

    def selected_cards(self):
        return list(self._map_provider.selected_cards())

    def _check_for_stepped_on_cards(self, actor_id, action, color):
        actor = self._actors[actor_id]
        stepped_on_card = self._map_provider.card_by_location(actor.location())
        # If the actor just moved and stepped on a card, mark it as selected.
        if (action.action_type == ActionType.TRANSLATE) and (
            stepped_on_card is not None
        ):
            logger.debug(
                f"Player {actor.actor_id()} stepped on card {str(stepped_on_card)}."
            )
            selected = not stepped_on_card.selected
            self._map_provider.set_selected(stepped_on_card.id, selected)
            self._map_provider.set_color(stepped_on_card.id, color)
            card_select_action = CardSelectAction(stepped_on_card.id, selected, color)
            self._announce_action(card_select_action)
            self._game_recorder.record_card_selection(actor, stepped_on_card)
            self._last_card_step_actor = actor
            clip_type = (
                SoundClipType.CARD_SELECT if selected else SoundClipType.CARD_DESELECT
            )
            self.queue_sound_clip(actor_id, clip_type)
            # If the follower selected a card, send the sound to the leader too.
            if actor.role() == Role.FOLLOWER:
                self.queue_leader_sound(clip_type)

    def drain_messages(self, id, messages):
        for message in messages:
            self._drain_message(id, message)

    def _drain_message(self, id, message):
        if message.type == message_to_server.MessageType.ACTIONS:
            logger.debug(f"Actions received. Room: {self._room_id}")
            self._drain_actions(id, message.actions)
        elif message.type == message_to_server.MessageType.OBJECTIVE:
            logger.debug(
                f"Objective received. Room: {self._room_id}, Text: {message.objective.text}"
            )
            self._drain_instruction(id, message.objective)
        elif message.type == message_to_server.MessageType.OBJECTIVE_COMPLETED:
            logger.debug(
                f"Objective Compl received. Room: {self._room_id}, uuid: {message.objective_complete.uuid}"
            )
            self._drain_instruction_complete(id, message.objective_complete)
            self._log_instructions()
        elif message.type == message_to_server.MessageType.TURN_COMPLETE:
            logger.debug(f"Turn Complete received. Room: {self._room_id}")
            self._drain_turn_complete(id, message.turn_complete)
        elif message.type == message_to_server.MessageType.STATE_SYNC_REQUEST:
            logger.debug(f"Sync request recvd. Room: {self._room_id}, Player: {id}")
            self.desync(id)
        elif message.type == message_to_server.MessageType.LIVE_FEEDBACK:
            logger.debug(f"Live feedback recvd. Room: {self._room_id}, Player: {id}")
            self._drain_live_feedback(id, message.live_feedback)
        elif message.type == message_to_server.MessageType.CANCEL_PENDING_OBJECTIVES:
            logger.debug(
                f"Cancel pending objectives recvd. Room: {self._room_id}, Player: {id}"
            )
            self._drain_cancel_pending_instructions(id)
        elif message.type == message_to_server.MessageType.SCENARIO_DOWNLOAD:
            # Compile a ScenarioState message and send it back to the client.
            logger.debug(
                f"Scenario download recvd. Room: {self._room_id}, Player: {id}"
            )
            self._drain_scenario_download(id)
        elif message.type == message_to_server.MessageType.FEEDBACK_RESPONSE:
            self._drain_feedback_response(id, message.feedback_response)
        else:
            logger.warn(f"Received unknown packet type: {message.type}")

    def _drain_feedback_response(self, id, feedback_response: FeedbackResponse):
        if id in self._unanswered_feedback_question:
            # Find the question that matches the response UUID.
            self._game_recorder.record_feedback_response(id, feedback_response)
            player_questions = self._unanswered_feedback_question[id]
            player_questions = [
                q for q in player_questions if q.uuid != feedback_response.uuid
            ]
            self._unanswered_feedback_question[id] = player_questions

    def _drain_actions(self, id, actions):
        for action in actions:
            logger.debug(f"{action.id}:{action.displacement}")
            self._drain_action(id, action)

    def _drain_action(self, actor_id, action):
        if action.id != actor_id:
            self.desync(actor_id)
            return
        self._actors[actor_id].add_action(action)

    def _drain_instruction(self, id, objective):
        if self._actors[id].role() != Role.LEADER:
            logger.warn(f"Warning, objective received from non-leader ID: {str(id)}")
            return
        if self._turn_state.turn != Role.LEADER:
            logger.warn(f"Warning, objective received out of turn.")
            return
        # TODO: Make UUID and non-UUID'd objectives separate message types.
        objective.uuid = uuid.uuid4().hex
        self._game_recorder.record_instruction_sent(objective)
        if len(self._instructions) == 0:
            self._game_recorder.record_instruction_activated(objective)
            self.queue_follower_sound(SoundClipType.INSTRUCTION_RECEIVED)
        self._instructions.append(objective)
        self._instruction_added = True
        for actor_id in self._actors:
            self._instructions_stale[actor_id] = True
        self.queue_leader_sound(SoundClipType.INSTRUCTION_SENT)

    def queue_leader_sound(self, clip_id: SoundClipType):
        if not self._leader:
            return
        self.queue_sound_clip(self._leader.actor_id(), clip_id)

    def queue_follower_sound(self, clip_id: SoundClipType):
        if not self._follower:
            return
        self.queue_sound_clip(self._follower.actor_id(), clip_id)

    def queue_sound_clip(self, player_id: int, clip_id: SoundClipType):
        if player_id not in self._actors:
            logger.warning(
                "Warning, sound clip received from non-actor ID: {str(player_id)}"
            )
            return
        if self._lobby is None or self._lobby.lobby_info() is None:
            return
        if player_id not in self._sound_trigger_messages:
            self._sound_trigger_messages[player_id] = []
        self._sound_trigger_messages[player_id].append(
            SoundTrigger(
                clip_id,
                self._lobby.lobby_info().sound_clip_volume,
            )
        )

    def _drain_instruction_complete(self, id, objective_complete):
        self._instruction_complete_queue.append((id, objective_complete))

    def _drain_live_feedback(self, id, feedback):
        if not config.GlobalConfig():
            logger.debug(f"Global config not set. Dropping message.")
            return
        feedback_enabled = (
            config.GlobalConfig().live_feedback_enabled
            or self._lobby.lobby_info().live_feedback_enabled
            or self._lobby.lobby_info().delayed_feedback_enabled
        )
        if not feedback_enabled:
            logger.debug(f"Live feedback disabled. Dropping message.")
            return
        if feedback.signal == live_feedback.FeedbackType.NONE:
            logger.debug(f"Received live feedback from {id} with type NONE. Dropping.")
            return
        if self._actors[id].role() != Role.LEADER:
            logger.warn(
                f"Warning, live feedback received from non-leader ID: {str(id)}"
            )
            return
        if self._turn_state.turn != Role.FOLLOWER:
            logger.warn(f"Warning, live feedback received during the leader's turn.")
            return
        sound_clip = (
            SoundClipType.POSITIVE_FEEDBACK
            if feedback.signal == live_feedback.FeedbackType.POSITIVE
            else SoundClipType.NEGATIVE_FEEDBACK
        )
        self.queue_leader_sound(sound_clip)
        self.queue_follower_sound(sound_clip)
        self._live_feedback_queue.append((id, feedback))

    def _drain_turn_complete(self, id, turn_complete):
        if self._actors[id].role() != self._turn_state.turn:
            logger.warn(
                f"Warning, turn complete received from ID: {str(id)} when it isn't their turn!"
            )
            return
        if self._actors[id].role() == Role.LEADER:
            if not self._has_instructions_todo():
                logger.warn(
                    f"Warning, turn complete received from leader ID: {str(id)} when there are no pending instructions!"
                )
                return
        if len(self._turn_complete_queue) >= 1:
            logger.warn(
                f"Warning, turn complete queued from ID: {str(id)}, but one was already received!"
            )
            return
        if self._actors[id].role() == Role.FOLLOWER and self._has_instructions_todo():
            logger.warn(
                f"Warning, turn complete received from ID: {str(id)} when there are pending instructions!"
            )
            return
        self._turn_complete_queue.append((id, "UserPrompted"))

    def _drain_cancel_pending_instructions(self, id):
        logger.debug(f"Cancel pending objectives received from ID: {str(id)}.")
        if self._actors[id].role() != Role.LEADER:
            logger.warn(
                f"Warning, objective cancellation from non-leader ID: {str(id)}"
            )
            return
        if self._actors[id].role() == self._turn_state.turn:
            logger.warn(
                f"Warning, objective cancellation from leader ID: {str(id)} when it is their turn!"
            )
            return
        # Queue up the cancellation.
        self._turn_complete_queue.append((id, "UserPromptedInterruption"))

    def _drain_scenario_download(self, id):
        self._scenario_download_pending[id] = True

    def _cancel_pending_instructions(self):
        # Cancel all objectives.
        while len(self._instructions) > 0:
            instruction = self._instructions.popleft()
            instruction.cancelled = True
            self._game_recorder.record_instruction_cancelled(instruction)
            self._instruction_history.append(instruction)

        for actor_id in self._actors:
            self._instructions_stale[actor_id] = True

    def create_actor(self, role):
        if role in self._preloaded_actors:
            self._actors_added = True
            actor = self._preloaded_actors[role]
            if role == Role.LEADER:
                self._leader = actor
            if role == Role.FOLLOWER:
                self._follower = actor
            del self._preloaded_actors[role]
            self._actors[actor.actor_id()] = actor
            self._action_history[actor.actor_id()] = []
            for actor_id in self._actors:
                self._prop_stale[actor_id] = True
            # Resend the latest turn state.
            self._resend_turn_state()
            self._mark_instructions_stale()
            # Mark clients as desynced.
            self.desync_all()
            return actor.actor_id()
        spawn_point = self._map_provider.consume_spawn_point()
        if spawn_point is None:
            spawn_point = HecsCoord(0, 0, 0)
        asset_id = AssetId.NONE
        if role == Role.LEADER:
            asset_id = AssetId.PLAYER
        elif role == Role.FOLLOWER:
            asset_id = AssetId.FOLLOWER_BOT
        actor = Actor(
            self._map_provider.id_assigner().alloc(),
            asset_id,
            role,
            spawn_point,
            realtime=self._realtime_actions,
        )
        if role == Role.LEADER:
            self._leader = actor
        if role == Role.FOLLOWER:
            self._follower = actor
        self._role_history[actor.actor_id()] = role
        self._actors[actor.actor_id()] = actor
        self._action_history[actor.actor_id()] = []
        # Resend the latest turn state.
        self._resend_turn_state()
        self._mark_instructions_stale()
        # Mark clients as desynced.
        self.desync_all()
        self._actors_added = True
        return actor.actor_id()

    def _mark_instructions_stale(self):
        for actor_id in self._actors:
            self._instructions_stale[actor_id] = True

    def free_actor(self, actor_id):
        if actor_id in self._actors:
            del self._actors[actor_id]
        if actor_id in self._action_history:
            del self._action_history[actor_id]
        if actor_id in self._instructions_stale:
            del self._instructions_stale[actor_id]
        if actor_id in self._turn_history:
            del self._turn_history[actor_id]
        # We don't free actor IDs. We'll never run out, and
        # keeping them from being re-used makes saving a history of which ID was
        # which role easier. Hence following line is commented:
        # self._map_provider.id_assigner().free(actor_id)
        #
        # Mark clients as desynced.
        self.desync_all()

    def get_actor(self, player_id):
        return self._actors[player_id]

    def desync(self, actor_id):
        self._synced[actor_id] = False

    def desync_all(self):
        for a in self._actors:
            actor = self._actors[a]
            self._synced[actor.actor_id()] = False

    def is_synced(self, actor_id):
        return self._synced[actor_id]

    def is_synced_all(self):
        for a in self._actors:
            if not self.synced(self._actors[a].actor_id()):
                return False
        return True

    def has_pending_messages(self):
        for actor_id in self._actors:
            if not self.is_synced(actor_id):
                return True
            if len(self._action_history.get(actor_id, [])) > 0:
                return True
            if self._instructions_stale.get(actor_id, False):
                return True
            if not self._turn_history.get(actor_id, Queue()).empty():
                return True
        return False

    def fill_messages(
        self, player_id, out_messages: List[message_from_server.MessageFromServer]
    ) -> bool:
        """Serializes all messages to one player into a linear history.

        If any messages have been generated this iteration, caps those
        messages with a StateMachineTick. This lets us separate logic
        iterations on the receive side.
        """
        message = self._next_message(player_id)
        messages_added = 0
        while message != None:
            out_messages.append(message)
            messages_added += 1
            message = self._next_message(player_id)

        if messages_added == 0:
            return False
        return True

    def _log_instructions(self):
        for objective in self._instructions:
            objective_status_char = "C" if objective.completed else "I"
            if objective.cancelled:
                objective_status_char = "X"
            logger.debug(
                f"\t {objective_status_char} | {objective.text} | {objective.uuid}"
            )

    def _next_message(self, player_id):
        actions = self._next_actions(player_id)
        if len(actions) > 0:
            logger.debug(
                f"Room {self._room_id} {len(actions)} actions for player_id {player_id}"
            )
            msg = message_from_server.ActionsFromServer(actions)
            return msg

        map_update = self._next_map_update(player_id)
        if map_update is not None:
            logger.debug(
                f"Room {self._room_id} map update {map_update} for player_id {player_id}"
            )
            return message_from_server.MapUpdateFromServer(map_update)

        prop_update = self._next_prop_update(player_id)
        if prop_update is not None:
            logger.debug(
                f"Room {self._room_id} prop update with {len(prop_update.props)} for player_id {player_id}"
            )
            return message_from_server.PropUpdateFromServer(prop_update)

        if not self.is_synced(player_id):
            state_sync = self._sync_message_for_transmission(player_id)
            logger.debug(
                f"Room {self._room_id} state sync: {state_sync} for player_id {player_id}"
            )
            logger.debug(
                f"State sync with {player_id} and # {len(state_sync.actors)} actors"
            )
            msg = message_from_server.StateSyncFromServer(state_sync)
            return msg

        objectives = self._next_instructions(player_id)
        if len(objectives) > 0:
            logger.debug(
                f"Room {self._room_id} {len(objectives)} texts for player_id {player_id}"
            )
            msg = message_from_server.ObjectivesFromServer(objectives)
            return msg

        turn_state = self._next_turn_state(player_id)
        if not turn_state is None:
            logger.debug(
                f"Room {self._room_id} ts {turn_state} for player_id {player_id}"
            )
            msg = message_from_server.GameStateFromServer(turn_state)
            return msg

        live_feedback = self._next_live_feedback(player_id)
        if not live_feedback is None:
            logger.debug(
                f"Room {self._room_id} live feedback {live_feedback} for player_id {player_id}"
            )
            msg = message_from_server.LiveFeedbackFromServer(live_feedback)
            return msg

        scenario_response = self._next_scenario_response(player_id)
        if not scenario_response is None:
            logger.debug(
                f"Room {self._room_id} scenario response {scenario_response} for player_id {player_id}"
            )
            msg = message_from_server.ScenarioResponseFromServer(scenario_response)
            return msg

        feedback_question = self._next_feedback_question(player_id)
        if not feedback_question is None:
            logger.debug(
                f"Room {self._room_id} feedback question {feedback_question} for player_id {player_id}"
            )
            msg = message_from_server.FeedbackQuestionFromServer(feedback_question)
            return msg

        tick = self._next_tick(player_id)
        if not tick is None:
            logger.debug(f"Room {self._room_id} tick {tick} for player_id {player_id}")
            msg = message_from_server.StateMachineTickFromServer(tick)
            return msg

        sound_trigger = self._next_sound_trigger(player_id)
        if not sound_trigger is None:
            logger.debug(
                f"Room {self._room_id} sound trigger {sound_trigger} for player_id {player_id}"
            )
            msg = message_from_server.SoundTriggerFromServer(sound_trigger)
            return msg

        # Nothing to send.
        return None

    def _next_sound_trigger(self, player_id):
        if not player_id in self._sound_trigger_messages:
            return None
        if len(self._sound_trigger_messages[player_id]) == 0:
            return None
        return self._sound_trigger_messages[player_id].pop()

    def _next_actions(self, actor_id):
        if not actor_id in self._action_history:
            return []
        action_history = self._action_history[actor_id]

        if len(action_history) == 0:
            return []

        # Log actions sent to client.
        self._action_history[actor_id] = []
        return action_history

    def _next_instructions(self, actor_id):
        if not actor_id in self._instructions_stale:
            self._instructions_stale[actor_id] = True

        if not self._instructions_stale[actor_id]:
            return []

        # Send the latest objective list and mark as fresh for this player.
        self._instructions_stale[actor_id] = False

        # For Leaders/Spectators it's simple, send the current objective list.
        if self._actors[actor_id].role() in [Role.LEADER, Role.SPECTATOR]:
            return list(self._instruction_history) + list(self._instructions)

        follower_instructions = list(self._instruction_history)
        # Also add the active instruction. Followers can see that too.
        if len(self._instructions) > 0:
            follower_instructions.append(self._instructions[0])
        return follower_instructions

    def _next_map_update(self, actor_id):
        if not actor_id in self._map_stale:
            self._map_stale[actor_id] = True

        if not self._map_stale[actor_id]:
            return None

        self._map_update_count += 1

        map_update = self._map_update

        if self._actors[actor_id].role() == Role.FOLLOWER:
            map_update = map_utils.CensorMapForFollower(
                map_update, self._actors[actor_id]
            )

        # Send the latest map and mark as fresh for this player.
        self._map_stale[actor_id] = False
        return map_update

    def _next_prop_update(self, actor_id):
        if not actor_id in self._prop_stale:
            self._prop_stale[actor_id] = True

        if not self._prop_stale[actor_id]:
            return None

        prop_update = self._prop_update

        self._prop_stale[actor_id] = False
        return prop_update

    def _next_live_feedback(self, actor_id):
        if actor_id not in self._live_feedback:
            return None
        if self._live_feedback[actor_id] == live_feedback.FeedbackType.NONE:
            return None
        feedback = live_feedback.LiveFeedbackFromType(self._live_feedback[actor_id])
        self._live_feedback[actor_id] = live_feedback.FeedbackType.NONE
        return feedback

    def _next_tick(self, player_id):
        if player_id not in self._ticks:
            return None
        tick = self._ticks[player_id]
        self._ticks[player_id] = None
        return tick

    def _next_scenario_response(self, player_id):
        if player_id not in self._scenario_download:
            return None
        scenario_download = self._scenario_download[player_id]
        del self._scenario_download[player_id]
        return ScenarioResponse(
            ScenarioResponseType.SCENARIO_DOWNLOAD, scenario_download
        )

    def _next_feedback_question(self, player_id):
        if player_id not in self._feedback_questions:
            return None
        # pop(0) is inefficient, but this list should only be a few elements
        # long at a time -- a human has to answer these questions in realtime,
        # after all.
        feedback_question = self._feedback_questions[player_id].pop(0)
        if len(self._feedback_questions[player_id]) == 0:
            return None
        return feedback_question

    # Returns the current state of the game.
    def state(self, actor_id=-1):
        actor_states = []
        for a in self._actors:
            actor = self._actors[a]
            actor_states.append(actor.state())
        role = self._actors[actor_id].role() if actor_id >= 0 else Role.NONE
        return state_sync.StateSync(len(self._actors), actor_states, actor_id, role)

    # Returns the current state of the game.
    # Calling this message comes with the assumption that the response will be transmitted to the clients.
    # Once this function returns, the clients are marked as synchronized.
    def _sync_message_for_transmission(self, actor_id):
        # This won't do... there might be some weird oscillation where an
        # in-flight invalid packet triggers another sync. need to communicate
        # round trip.
        sync_message = self.state(actor_id)
        self._synced[actor_id] = True
        return sync_message

    def _valid_action(self, actor_id, action):
        if action.action_type == ActionType.TRANSLATE:
            cartesian = action.displacement.cartesian()
            # Add a small delta for floating point comparison.
            if math.sqrt(cartesian[0] ** 2 + cartesian[1] ** 2) > 1.001:
                logger.debug(f"Invalid action: translation too large {action}")
                return False
            destination = HecsCoord.add(
                self._actors[actor_id].location(), action.displacement
            )
            if self._map_provider.edge_between(
                self._actors[actor_id].location(), destination
            ):
                logger.debug(f"Invalid action: attempts to move through wall {action}")
                return False
            forward_location = (
                self._actors[actor_id]
                .location()
                .neighbor_at_heading(self._actors[actor_id].heading_degrees())
            )
            backward_location = (
                self._actors[actor_id]
                .location()
                .neighbor_at_heading(self._actors[actor_id].heading_degrees() + 180)
            )
            if destination not in [forward_location, backward_location]:
                logger.debug(
                    f"Invalid action: attempts to move to {destination.to_offset_coordinates()} which is invalid. Facing: {self._actors[actor_id].heading_degrees()} backward location: {backward_location.to_offset_coordinates()}. exp: {action.expiration}"
                )
                return False
        if action.action_type == ActionType.ROTATE:
            if abs(action.rotation) > 60.01:
                logger.debug(f"Invalid action: attempts to rotate too much {action}")
                return False
        return True

    def _handle_instruction_complete(self, id, objective_complete):
        if self._actors[id].role() != Role.FOLLOWER:
            logger.warn(
                f"Warning, obj complete received from non-follower ID: {str(id)}"
            )
            return
        if len(self._instructions) == 0:
            logger.warn(
                f"Warning, obj complete received with no instructions ID: {str(id)}"
            )
            return
        if self._instructions[0].uuid != objective_complete.uuid:
            logger.warn(
                f"Warning, obj complete received with wrong uuid ID: {objective_complete.uuid}"
            )
            return
        if self._instructions[0].cancelled:
            logger.warn(
                f"Warning, obj complete received for cancelled objective ID: {objective_complete.uuid}"
            )
            return
        active_instruction = self._instructions.popleft()
        active_instruction.completed = True
        self._instruction_history.append(active_instruction)
        self._game_recorder.record_instruction_complete(objective_complete)
        if len(self._instructions) > 0:
            self._game_recorder.record_instruction_activated(self._instructions[0])
            self.queue_follower_sound(SoundClipType.INSTRUCTION_RECEIVED)
        for actor_id in self._actors:
            self._instructions_stale[actor_id] = True

    def _set_scenario(
        self,
        scenario: Scenario,
        realtime_actions: bool = True,
        delayed_actor_load: bool = False,
    ):
        """Modify current game state to match the given scenario. Wipes existing game state.

        Args:
            scenario: The scenario to load.
            realtime_actions: Whether to enable realtime actions.
            delayed_actor_load: If actor loading is delayed, then actor
                state is preloaded and later players will init with their state.
        """
        # If the scenario is packaged with any kvals and the game_record is populated, then
        # we should add the kvals to the game_record.
        if scenario.kvals and self._game_recorder.kvals() is not None:
            kvals = self._game_recorder.kvals()
            for scenario_key in scenario.kvals:
                kvals[scenario_key] = scenario.kvals[scenario_key]
            self._game_recorder.set_kvals(kvals)
        # Clear existing states.
        self._instruction_history = deque()
        self._turn_complete_queue = deque()
        self._instruction_complete_queue = deque()
        self._live_feedback_queue = deque()
        self._preloaded_actors = {}
        # Load in map & props.
        props = scenario.prop_update.props
        cards = [Card.FromProp(prop) for prop in props]
        self._map_provider = MapProvider(
            MapType.PRESET, scenario.map, cards, custom_targets=scenario.target_card_ids
        )
        self._map_update = self._map_provider.map()
        self._prop_update = self._map_provider.prop_update()
        self._prop_update = map_utils.CensorCards(self._prop_update, None)
        # Load in instructions.
        self._instructions = deque(scenario.objectives)
        # Load in actor states.
        leader_id = None
        follower_id = None
        for actor_id, actor in self._actors.items():
            if actor.role() == Role.LEADER:
                leader_id = actor_id
            elif actor.role() == Role.FOLLOWER:
                follower_id = actor_id
        # If leader and follower are still None, then we need to create them.
        if leader_id is None:
            if delayed_actor_load:
                leader_id = self._map_provider.id_assigner().alloc()
            else:
                leader_id = self.create_actor(Role.LEADER)
        if follower_id is None:
            if delayed_actor_load:
                follower_id = self._map_provider.id_assigner().alloc()
            else:
                follower_id = self.create_actor(Role.FOLLOWER)
        for actor_state in scenario.actor_state.actors:
            if actor_state.actor_role == Role.LEADER:
                actor_state = dataclasses.replace(actor_state, actor_id=leader_id)
                actor = Actor.from_state(actor_state, realtime_actions)
                if not delayed_actor_load:
                    self._actors[leader_id] = actor
                    self._leader = actor
                else:
                    self._preloaded_actors[Role.LEADER] = actor
            elif actor_state.actor_role == Role.FOLLOWER:
                actor_state = dataclasses.replace(actor_state, actor_id=follower_id)
                actor = Actor.from_state(actor_state, realtime_actions)
                if not delayed_actor_load:
                    self._actors[follower_id] = actor
                    self._follower = self._actors[follower_id]
                else:
                    self._preloaded_actors[Role.FOLLOWER] = actor
        if (self._leader is None and not delayed_actor_load) or (
            Role.LEADER not in self._preloaded_actors and delayed_actor_load
        ):
            logger.warn("Warning, scenario did not contain leader")
        if (self._follower is None and not delayed_actor_load) or (
            Role.FOLLOWER not in self._preloaded_actors and delayed_actor_load
        ):
            logger.warn("Warning, scenario did not contain follower")
        # Mark everything as stale.
        self._mark_map_stale()
        self._mark_prop_stale()
        self._mark_instructions_stale()
        # Mark clients as desynced.
        self.desync_all()
        self._send_turn_state(scenario.turn_state)
        self._self_initialize()

    def _get_scenario(self, player_id: int, scenario_id: str) -> Scenario:
        """Convert the current game state into a scenario object, that can be saved to a file or passed to _set_scenario(...)."""
        props = [card.prop() for card in self._map_provider.cards()]
        states = [actor.state() for actor in self._actors.values()]
        state_sync_msg = state_sync.StateSync(
            len(self._actors), states, player_id, self._actors[player_id].role()
        )
        return Scenario(
            scenario_id,
            self._map_provider.map(),
            PropUpdate(props),
            self._turn_state,
            list(self._instructions),
            state_sync_msg,
        )

    def _mark_map_stale(self):
        for id in self._map_stale:
            self._map_stale[id] = True

    def _mark_prop_stale(self):
        for id in self._prop_stale:
            self._prop_stale[id] = True

    def _send_turn_state(self, turn_state, reason=""):
        # Avoid unnecessary database writes.
        if self._turn_state == turn_state:
            return
        self._turn_state = turn_state
        for actor_id in self._actors:
            if not actor_id in self._turn_history:
                self._turn_history[actor_id] = Queue()
            self._turn_history[actor_id].put(dataclasses.replace(turn_state))

    def _resend_turn_state(self):
        if self._turn_state is None:
            return
        for actor_id in self._actors:
            if not actor_id in self._turn_history:
                self._turn_history[actor_id] = Queue()
            self._turn_history[actor_id].put(dataclasses.replace(self._turn_state))

    def _next_turn_state(self, actor_id):
        if not actor_id in self._turn_history:
            self._turn_history[actor_id] = Queue()
        try:
            turn = self._turn_history[actor_id].get_nowait()
            return turn
        except queue.Empty:
            return None
