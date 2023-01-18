import dataclasses
import logging
import math
import queue
import random
import uuid
from collections import deque
from datetime import datetime, timedelta
from queue import Queue
from typing import List

import orjson

import server.config.config as config
import server.google_experience as google_experience
import server.leaderboard as leaderboard
import server.map_utils as map_utils
import server.mturk_experience as mturk_experience
import server.schemas.game as game_db
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
    objective,
    state_sync,
)
from server.messages.action import Action, ActionType, Color
from server.messages.map_update import MapUpdate
from server.messages.prop import Prop, PropUpdate
from server.messages.rooms import Role
from server.messages.scenario import Scenario, ScenarioResponse, ScenarioResponseType
from server.messages.state_sync import StateMachineTick
from server.messages.turn_state import GameOverMessage, TurnState, TurnUpdate
from server.schemas.event import Event, EventOrigin, EventType
from server.schemas.util import InitialState
from server.util import CountDownTimer

LEADER_MOVES_PER_TURN = 5
FOLLOWER_MOVES_PER_TURN = 10

LEADER_SECONDS_PER_TURN = 50
FOLLOWER_SECONDS_PER_TURN = 15

FOLLOWER_TURN_END_DELAY_SECONDS = 1

logger = logging.getLogger(__name__)


def turn_reward(score):
    """Calculates the turn reward (# of turns added) for a given score."""
    if score == 0:
        return 5
    elif score in [1, 2]:
        return 4
    elif score in [3, 4]:
        return 3
    elif score in [5, 6]:
        return 2
    elif score in [7, 8]:
        return 1
    else:
        return 0


def cumulative_turns_added(score):
    """Calculates the cumulative extra turns added since the start of the game for a given score."""
    turns = 0
    for i in range(score):
        turns += turn_reward(i)
    return turns


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
        cls, room_id, event_uuid: str = "", realtime_actions: bool = False
    ):
        """Initialize the game from a given event.

        Returns: (state_machine: State, failure_reason: str = "")

        If return value state_machine is none, the reason for failure is in failure_reason.
        """
        event_query = (
            Event.select().join(game_db.Game).where(Event.id == event_uuid).limit(1)
        )
        if event_query.count() != 1:
            return (
                None,
                f"1 Event {event_uuid} not found. ({event_query.count()} found)",
            )
        event = event_query.get()
        game_record = event.game

        game_events = (
            Event.select()
            .where(Event.game == game_record, Event.server_time <= event.server_time)
            .order_by(Event.server_time)
        )

        map_event = game_events.where(Event.type == EventType.MAP_UPDATE).get()
        map_update = MapUpdate.from_json(map_event.data)

        prop_event = game_events.where(Event.type == EventType.PROP_UPDATE).get()
        prop_update = PropUpdate.from_json(prop_event.data)
        cards = [Card.FromProp(prop) for prop in prop_update.props]
        cards_by_loc = {}
        for card in cards:
            cards_by_loc[card.location] = card

        card_events = game_events.where(
            Event.type
            << [EventType.CARD_SET, EventType.CARD_SPAWN, EventType.CARD_SELECT]
        ).order_by(Event.server_time)

        # Integrate all cardset and card spawn events up to the given event, to get the current card state
        for event in card_events:
            if event.type == EventType.CARD_SET:
                data = orjson.loads(event.data)
                set_cards = [Card.from_dict(card) for card in data["cards"]]
                # Clear cards that were in the set
                for card in set_cards:
                    cards_by_loc[card.location] = None
            if event.type == EventType.CARD_SPAWN:
                data = orjson.loads(event.data)
                card = Card.from_dict(data)
                cards_by_loc[card.location] = card
            if event.type == EventType.CARD_SELECT:
                card = Card.from_json(event.data)
                cards_by_loc[card.location] = card

        cards = cards_by_loc.values()
        # Filter out None values
        cards = [card for card in cards if card is not None]
        logger.debug(f"Detected {len(cards)} cards in the game. at this point.")

        turn_record_query = game_events.where(
            Event.type << [EventType.TURN_STATE, EventType.START_OF_TURN]
        ).order_by(Event.server_time.desc())
        if turn_record_query.count() == 0:
            # Initial turn.
            turn_record = TurnUpdate(
                Role.LEADER,
                LEADER_MOVES_PER_TURN,
                6,
                datetime.utcnow() + State._turn_duration(Role.LEADER),
                datetime.utcnow(),
                0,
                0,
                0,
            )
        else:
            turn_record = turn_record_query.get()

        turn_state = TurnState.from_json(turn_record.data)

        # Integrate all instruction events up to the given event, to get the current instruction state
        instruction_list = []
        instruction_events = game_events.where(
            Event.type
            << [
                EventType.INSTRUCTION_SENT,
                EventType.INSTRUCTION_ACTIVATED,
                EventType.INSTRUCTION_CANCELLED,
                EventType.INSTRUCTION_DONE,
            ]
        ).order_by(Event.server_time)
        for event in instruction_events:
            if event.type == EventType.INSTRUCTION_SENT:
                instruction_list.append(
                    objective.ObjectiveMessage.from_json(event.data)
                )
                logger.info(f"Sent: {instruction_list[-1].uuid}")
            if event.type == EventType.INSTRUCTION_ACTIVATED:
                parent_instruction_event = event.parent_event
                instruction = objective.ObjectiveMessage.from_json(
                    parent_instruction_event.data
                )
                logger.info(f"Activated: {instruction.uuid}")
                if instruction_list[0].uuid != instruction.uuid:
                    for instruction in instruction_list:
                        logger.info(f"Instruction: {instruction.uuid}")
                    return (
                        None,
                        f"Activated instruction {instruction.uuid} not found in instruction list.",
                    )
            if event.type == EventType.INSTRUCTION_CANCELLED:
                parent_instruction_event = event.parent_event
                instruction = objective.ObjectiveMessage.from_json(
                    parent_instruction_event.data
                )
                if instruction_list[0].uuid != instruction.uuid:
                    return (
                        None,
                        f"Cancelled instruction {event.data} not found in instruction list.",
                    )
                if len(instruction_list) > 0:
                    logger.info(f"Cancelled: {instruction_list[0].uuid}")
                    # Delete the instruction from the list.
                    instruction_list = instruction_list[1:]
            if event.type == EventType.INSTRUCTION_DONE:
                parent_instruction_event = event.parent_event
                instruction = objective.ObjectiveMessage.from_json(
                    parent_instruction_event.data
                )
                logger.info(f"Done: {instruction_list[0].uuid}")
                # Make sure this instruction is at the head of the list.
                if instruction_list[0].uuid != instruction.uuid:
                    return (
                        None,
                        f"Done instruction {event.data} not found in instruction list.",
                    )
                # Delete the instruction from the list.
                instruction_list = instruction_list[1:]

        initial_state_event = game_events.where(
            Event.type == EventType.INITIAL_STATE,
        )
        if initial_state_event.count() != 1:
            return (
                None,
                f"Single initial state event not found. ({initial_state_event.count()} found)",
            )
        initial_state_event = initial_state_event.get()
        initial_state = InitialState.from_json(initial_state_event.data)

        leader = Actor(
            21,
            0,
            Role.LEADER,
            initial_state.leader_position,
            realtime_actions,
            initial_state.leader_rotation_degrees,
        )
        follower = Actor(
            22,
            0,
            Role.FOLLOWER,
            initial_state.follower_position,
            realtime_actions,
            initial_state.follower_rotation_degrees,
        )

        moves = game_events.where(Event.type == EventType.ACTION)
        logger.debug(f"Found {moves.count()} moves before event {event_uuid}")
        for move in moves:
            action = Action.from_json(move.data)
            if action.action_type not in [
                ActionType.INIT,
                ActionType.INSTANT,
                ActionType.ROTATE,
                ActionType.TRANSLATE,
            ]:
                continue
            if move.origin == EventOrigin.LEADER:
                leader.add_action(action)
                leader.step()
            elif move.origin == EventOrigin.FOLLOWER:
                follower.add_action(action)
                follower.step()
            else:
                return None, f"Unknown event origin: {move.origin}"
        s = State(
            room_id,
            None,
            True,
            map_update,
            [card.prop() for card in cards],
            turn_state,
            instruction_list,
            [leader, follower],
            realtime_actions=realtime_actions,
            log_to_db=False,
        )
        return s, ""

    def _set_scenario(
        self,
        scenario: Scenario,
        realtime_actions: bool = True,
    ):
        props = scenario.prop_update.props
        cards = [Card.FromProp(prop) for prop in props]
        self._map_provider = MapProvider(MapType.PRESET, map, cards)
        self._instructions = deque(scenario.objectives)
        self._instruction_history = deque()
        self._instructions_stale = {}
        self._turn_complete_queue = deque()
        self._instruction_complete_queue = deque()
        self._live_feedback_queue = deque()
        self._preloaded_actors = {}
        for actor_state in scenario.actor_state:
            new_actor = Actor.from_state(actor_state, realtime_actions)
            self._preloaded_actors[new_actor.role()] = new_actor
        self._send_turn_state(scenario.turn_state)

    def _get_scenario(self, player_id: int) -> Scenario:
        props = [card.prop() for card in self._map_provider.cards()]
        states = [actor.state() for actor in self._actors.values()]
        state_sync_msg = state_sync.StateSync(
            len(self._actors), states, player_id, self._actors[player_id].role()
        )
        return Scenario(
            self._map_provider.map(),
            PropUpdate(props),
            self._turn_state,
            list(self._instructions),
            state_sync_msg,
        )

    def _init_from_data(
        self,
        map,
        props,
        turn_state,
        instructions,
        actors,
        realtime_actions: bool = False,
    ):
        self._game_recorder = GameRecorder(None, disabled=True)
        scenario = Scenario(
            map,
            PropUpdate(props),
            turn_state,
            instructions,
            [actor.state() for actor in actors],
        )
        self._set_scenario(scenario, realtime_actions)

    def __init__(
        self,
        room_id,
        game_record,
        use_preset_data: bool = False,
        map: MapUpdate = None,
        props: List[Prop] = [],
        turn_state: TurnState = None,
        instructions: List[objective.ObjectiveMessage] = [],
        actors: List[Actor] = [],
        log_to_db: bool = True,
        realtime_actions: bool = False,
    ):
        self._start_time = datetime.utcnow()
        self._room_id = room_id

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
            self._init_from_data(
                map, props, turn_state, instructions, actors, realtime_actions
            )
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
                datetime.utcnow() + State._turn_duration(Role.LEADER),
                datetime.utcnow(),
                0,
                0,
                0,
            )
            self._send_turn_state(initial_turn)

        self._id_assigner = (
            self._map_provider.id_assigner()
        )  # Map and state props share the same ID space.

        self._map_update = self._map_provider.map()
        # Maps from player_id -> list of props to update.
        self._prop_update = self._map_provider.prop_update()

        # Maps from player_id -> live_feedback.FeedbackType if live feedback is
        # pending. Otherwise live_feedback.FeedbackType.None.
        self._live_feedback = {}

        self._spawn_points = self._map_provider.spawn_points()
        random.shuffle(self._spawn_points)
        self._done = False

        self._current_set_invalid = self._map_provider.selected_cards_collide()
        # Adds card covers.
        self._prop_update = map_utils.CensorCards(self._prop_update, None)

    def game_time(self):
        """Return timedelta between now and when the game started."""
        return datetime.utcnow() - self._start_time

    @classmethod
    def _turn_duration(self, role):
        return (
            timedelta(seconds=LEADER_SECONDS_PER_TURN)
            if role == Role.LEADER
            else timedelta(seconds=FOLLOWER_SECONDS_PER_TURN)
        )

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
            kvals["disconnected"].push(role.name)
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
            # Find the follower. TODO(sharf): cleanup code like this in the file...
            follower = None
            for actor_id in self._actors:
                if self._actors[actor_id].role() == Role.FOLLOWER:
                    follower = self._actors[actor_id]
                    break
            send_tick = True
            active_instruction = None
            if len(self._instructions) > 0:
                active_instruction = self._instructions[0]
            self._game_recorder.record_live_feedback(
                feedback, follower, active_instruction
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
            self._follower_turn_end_reason = ""
            logger.debug(f"Follower Turn Ended.")
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
                    self._game_recorder._announce_action(
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
                self._scenario_download[actor_id] = self._get_scenario(actor_id)

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

    def on_game_over(self):
        logger.info(f"Game {self._room_id} is over.")
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
        opposite_role = (
            Role.LEADER if self._turn_state.turn == Role.FOLLOWER else Role.FOLLOWER
        )
        role_switch = (
            datetime.utcnow() >= self._turn_state.turn_end
        ) or force_role_switch
        next_role = opposite_role if role_switch else self._turn_state.turn
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
            turn_end = datetime.utcnow() + State._turn_duration(next_role)
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
        else:
            logger.warn(f"Received unknown packet type: {message.type}")

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
        self._instructions.append(objective)
        self._instruction_added = True
        for actor_id in self._actors:
            self._instructions_stale[actor_id] = True

    def _drain_instruction_complete(self, id, objective_complete):
        self._instruction_complete_queue.append((id, objective_complete))

    def _drain_live_feedback(self, id, feedback):
        if config.GlobalConfig() and not config.GlobalConfig().live_feedback_enabled:
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
        logger.info(f"create_actor() Role: {role}")
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
        spawn_point = (
            self._spawn_points.pop() if self._spawn_points else HecsCoord(0, 0, 0)
        )
        asset_id = AssetId.PLAYER if role == Role.LEADER else AssetId.FOLLOWER_BOT
        actor = Actor(
            self._id_assigner.alloc(),
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
        # self._id_assigner.free(actor_id)
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
            if len(self._action_history[actor_id]) > 0:
                return True
            if self._instructions_stale[actor_id]:
                return True
            if not self._turn_history[actor_id].empty():
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

        tick = self._next_tick(player_id)
        if not tick is None:
            logger.debug(f"Room {self._room_id} tick {tick} for player_id {player_id}")
            msg = message_from_server.StateMachineTickFromServer(tick)
            return msg

        # Nothing to send.
        return None

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

        # For Leaders it's simple, send the current objective list.
        if self._actors[actor_id].role() == Role.LEADER:
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
            ScenarioResponseType.SCENARIO_DOWNLOAD, None, scenario_download
        )

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
        for actor_id in self._actors:
            self._instructions_stale[actor_id] = True
