from server.actor import Actor
from server.assets import AssetId
from server.messages.action import Action, Color, ActionType, CensorActionForFollower
from server.messages.map_update import MapUpdate
from server.messages.prop import Prop
from server.messages.rooms import Role
from server.messages import live_feedback, message_from_server
from server.messages import message_to_server
from server.messages import objective, state_sync
from server.hex import HecsCoord
from server.map_provider import MapProvider, MapType, CachedMapRetrieval
from server.card import CardSelectAction, SetCompletionActions, Card
from server.messages.turn_state import TurnState, GameOverMessage, TurnUpdate

from server.game_recorder import GameRecorder
from server.state_machine_driver import StateMachineDriver

import server.config.config as config
import server.experience as experience
import server.leaderboard as leaderboard
import server.schemas.game as game_db
import server.schemas.cards as cards_db
import server.schemas.map as map_db

from collections import deque
from datetime import datetime, timedelta
from queue import Queue
from typing import List

from server.schemas.base import GetDatabase

import asyncio
import copy
import dataclasses
import logging
import math
import random
import uuid
import queue

import server.map_utils as map_utils
from server.messages.state_sync import StateMachineTick

LEADER_MOVES_PER_TURN = 5
FOLLOWER_MOVES_PER_TURN = 10

LEADER_SECONDS_PER_TURN = 50
FOLLOWER_SECONDS_PER_TURN = 15

logger = logging.getLogger(__name__)

def turn_reward(score):
    """ Calculates the turn reward (# of turns added) for a given score. """
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
    """ Calculates the cumulative extra turns added since the start of the game for a given score. """
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
    def InitializeFromExistingState(cls, room_id, instruction_uuid: str = "", realtime_actions: bool = False):
        """ Initialize the game from a given instruction.

            Returns: (state_machine: State, failure_reason: str = "")

            If return value state_machine is none, the reason for failure is in failure_reason.
        """
        instruction_query = game_db.Instruction.select().join(game_db.Game).where(game_db.Instruction.uuid == instruction_uuid)
        if instruction_query.count() != 1:
            return None, f"Single instruction {instruction_uuid} not found. ({instruction_query.count()} found)"
        instruction_record = instruction_query.get()
        game_record = instruction_record.game
        turn_active = game_db.InstructionTurnActive(instruction_record)
        if len(instruction_record.moves) != 0:
            map_time = instruction_record.moves[0].server_time
            map = map_db.MapUpdate.select().where(map_db.MapUpdate.game == instruction_record.game, map_db.MapUpdate.time <= map_time).order_by(map_db.MapUpdate.time.desc()).get()
        else:
            # Hacky, for now just use map before instruction received. Several queued instructions in the meantime could have changed the map.
            logger.warn(f"Map reconstruction might not be accurate. Instruction had no moves, so exact timing of instruction activation unknown.")
            map = map_db.MapUpdate.select().where(map_db.MapUpdate.game == instruction_record.game, map_db.MapUpdate.time <= instruction_record.time).order_by(map_db.MapUpdate.time).get()

        turn_record_query = game_db.Turn.select().where(game_db.Turn.game == game_record, game_db.Turn.time <= instruction_record.time).order_by(game_db.Turn.time.desc())
        if turn_record_query.count() == 0:
            # Initial turn.
            turn_record = TurnUpdate(
                Role.LEADER, LEADER_MOVES_PER_TURN, 6,
                datetime.utcnow() + State.turn_duration(Role.LEADER),
                datetime.utcnow(), 0, 0, 0)
        else:
            turn_record = game_db.Turn.select().where(game_db.Turn.game == game_record, game_db.Turn.time <= instruction_record.time).order_by(game_db.Turn.time.desc()).get()

        last_set = cards_db.CardSets.select().join(game_db.Move).where(cards_db.CardSets.game == game_record, cards_db.CardSets.move.server_time <= instruction_record.time).order_by(cards_db.CardSets.move.server_time.desc())
        score = 0
        if last_set.count() != 0:
            score = last_set.get().score

        turns_left = 6 + cumulative_turns_added(score) - turn_record.turn_number
        logger.info(f"Turns left: {turns_left}. Start: 6, added: {cumulative_turns_added(score)}, current turn: {turn_record.turn_number}")
        turn_state = TurnState(
            Role.FOLLOWER,
            10, # moves.
            turns_left,
            datetime.utcnow() + timedelta(seconds=FOLLOWER_SECONDS_PER_TURN), # Time left.
            datetime.utcnow(), # Time started.
            score, # Sets collected.
            score, # Sets collected.
            turns_left < 0, # Game over.
            turn_record.turn_number)
        cards = []
        if len(map.map_data.props) != 0:
            logger.info(f"Loading cards from map, which contains {len(map.map_data.props)} cards.")
            cards = map.map_data.props
        else:
            logger.error(f"Map {map.id} has no props. Cannot recover cards.")

        instruction = objective.ObjectiveMessage(Role.LEADER, instruction_record.text, instruction_record.uuid, False, False)
        initial_state = game_db.InitialState.select().join(game_db.Game).where(game_db.Game.id == game_record.id).get()

        leader = Actor(21, 0, Role.LEADER, initial_state.leader_position, realtime_actions, initial_state.leader_rotation_degrees)
        follower = Actor(22, 0, Role.FOLLOWER, initial_state.follower_position, realtime_actions, initial_state.follower_rotation_degrees)

        moves = game_db.Move.select().join(game_db.Instruction).where(game_db.Move.game_id == game_record.id, game_db.Move.instruction.time < instruction_record.time)
        logger.info(f"Found {moves.count()} moves before instruction {instruction_record.uuid}")
        for move in moves:
            if move.character_role == "Role.LEADER":
                leader.add_action(move.action)
                leader.step()
            elif move.character_role == "Role.FOLLOWER":
                follower.add_action(move.action)
                follower.step()
            else:
                return None, f"Unknown character role {move.character_role}"
        s = State(room_id, None, True, map.map_data, cards, turn_state, [instruction], [leader, follower])
        return s, ""

    def _init_from_data(self, map, props, turn_state, instructions, actors, realtime_actions: bool = False):
        self._game_recorder = GameRecorder(None, disabled=True)
        cards = [Card.FromProp(prop) for prop in props]
        self._map_provider = MapProvider(MapType.PRESET, map, cards)
        self._instructions = deque(instructions)
        self._instruction_history = deque()
        self._instructions_stale = {}
        self._turn_complete_queue = deque()
        self._instruction_complete_queue = deque()
        self._preloaded_actors = {}
        for actor in actors:
            asset_id = AssetId.PLAYER if actor.role() == Role.LEADER else AssetId.FOLLOWER_BOT
            spawn_point = actor.location()
            new_actor = Actor(self._map_provider.id_assigner().alloc(), asset_id, actor.role(), spawn_point, realtime_actions, actor.heading_degrees())
            self._preloaded_actors[actor.role()] = new_actor
        self.send_turn_state(turn_state)
    
    def __init__(self, room_id, game_record, use_preset_data: bool = False, map: MapUpdate = None, props: List[Prop] = [], turn_state: TurnState = None, instructions: List[objective.ObjectiveMessage] = [], actors: List[Actor] = [], log_to_db: bool = True, realtime_actions: bool = False):
        self._room_id = room_id

        # Rolling count of iteration loop. Used to indicate when an iteration of
        # the logic loop has occurred. Sent out in StateMachineTick messages
        # (only if an event occured that loop).
        self._iter = 0

        # Maps from actor_id (prop id) to actor object (see definition below).
        self._actors = {}
        # True if a player was added since the last iteration.
        self._actors_added = False
        self._realtime_actions = realtime_actions

        self._turn_complete_queue = deque()

        self._instructions = deque() # A list of unprocessed instructions.
        self._instruction_history = deque() # All instructions, including completed/cancelled ones.
        self._instructions_stale = {}  # Maps from player_id -> bool if their objective list is stale.
        self._instruction_added = False # True if an instruction was added since the last iteration.
        self._instruction_complete_queue = deque()

        self._map_stale = {} # Maps from player_id -> bool if their map is stale.
        self._map_update_count = 0

        self._prop_stale = {} # Maps from player_id -> bool if their prop list is stale.

        self._ticks = {} # Maps from player_id -> tick message.

        self._synced = {}
        self._action_history = {}
        self._turn_history = {}

        self._preloaded_actors = {}
        
        self._turn_state = None

        if use_preset_data:
            self._init_from_data(map, props, turn_state, instructions, actors, realtime_actions)
        else:
            # Records everything that happens in a game.
            self._game_recorder = GameRecorder(game_record) if log_to_db else GameRecorder(None, disabled=True)
            # Map props and actors share IDs from the same pool, so the ID assigner
            # is shared to prevent overlap.
            self._map_provider = CachedMapRetrieval()
            initial_turn = TurnUpdate(
                Role.LEADER, LEADER_MOVES_PER_TURN, 6,
                datetime.utcnow() + State.turn_duration(Role.LEADER),
                datetime.utcnow(), 0, 0, 0)
            self.send_turn_state(initial_turn)

        self._id_assigner = self._map_provider.id_assigner()  # Map and state props share the same ID space.

        self._map_update = self._map_provider.map()
        self._prop_update = self._map_provider.prop_update() # Maps from player_id -> list of props to update.

        self._live_feedback = {} # Maps from player_id -> live_feedback.FeedbackType if live feedback is pending. Otherwise live_feedback.FeedbackType.None.

        self._spawn_points = self._map_provider.spawn_points()
        random.shuffle(self._spawn_points)
        self._done = False

        self._current_set_invalid = self._map_provider.selected_cards_collide()

    @classmethod
    def turn_duration(self, role):
        return timedelta(seconds=LEADER_SECONDS_PER_TURN) if role == Role.LEADER else timedelta(seconds=FOLLOWER_SECONDS_PER_TURN)

    def send_turn_state(self, turn_state):
        # Avoid unnecessary database writes.
        if self._turn_state == turn_state:
            return
        # Record a copy of the current turn state.
        self._game_recorder.record_turn_state(turn_state)
        self._turn_state = turn_state
        for actor_id in self._actors:
            if not actor_id in self._turn_history:
                self._turn_history[actor_id] = Queue()
            self._turn_history[actor_id].put(
                dataclasses.replace(turn_state))
    
    def resend_turn_state(self):
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
        logger.info(f"Game ending.")
        self._done = True

    def record_action(self, action):
        # Marks an action as validated (i.e. it did not conflict with other actions).
        # Queues this action to be sent to each user.
        for id in self._actors:
            actor = self._actors[id]
            self._action_history[actor.actor_id()].append(action)

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
        self._game_recorder.initial_state(self._map_provider.map(), self._map_provider.prop_update(), self._turn_state, self._actors)

    def update(self):
        send_tick = False

        # Have we received an instruction since the last iteration?
        if self._instruction_added:
            self._instruction_added = False
            send_tick = True
        
        if self._actors_added:
            self._actors_added = False
            send_tick = True

        if datetime.utcnow() >= self._turn_state.turn_end:
            self.update_turn()
            send_tick = True

        # Handle actor actions.
        for actor_id in self._actors:
            actor = self._actors[actor_id]
            while actor.has_actions():
                logger.info(f"Actor {actor_id} has pending actions.")
                proposed_action = actor.peek()
                if not self._turn_state.turn == actor.role():
                    actor.drop()
                    self.desync(actor_id)
                    logger.info(
                        f"Actor {actor_id} is not the current role. Dropping pending action.")
                    send_tick = True
                    continue
                if self._turn_state.moves_remaining == 0:
                    actor.drop()
                    self.desync(actor_id)
                    logger.info(
                        f"Actor {actor_id} is out of moves. Dropping pending action.")
                    send_tick = True
                    continue

                if not self.valid_action(actor_id, proposed_action):
                    actor.drop()
                    self.desync(actor_id)
                    send_tick = True
                    continue
                
                if ((not actor.is_realtime) or actor.peek_action_done()):
                    self._game_recorder.record_move(actor, proposed_action)
                    actor.step()
                    self.record_action(proposed_action)
                    color = Color(0, 0, 1, 1) if not self._current_set_invalid else Color(1, 0, 0, 1)
                    self.check_for_stepped_on_cards(actor_id, proposed_action, color)
                    self.update_turn()
                    send_tick = True

        if self._turn_state.turn == Role.FOLLOWER and self._turn_state.moves_remaining <= 0:
            self.update_turn(force_role_switch=True, end_reason="FollowerOutOfMoves")
            send_tick = True
        
        while len(self._turn_complete_queue) > 0:
            (id, reason) = self._turn_complete_queue.popleft()
            if id not in self._actors:
                continue
            actor = self._actors[id]
            if actor.role() == self._turn_state.turn:
                self.update_turn(force_role_switch=True, end_reason=reason)
                send_tick = True
                continue
            # The leader can end the follower's turn via an interruption
            if actor.role() == Role.LEADER and reason == "UserPromptedInterruption":
                self.cancel_pending_instructions()
                self.update_turn(force_role_switch=True, end_reason=reason)
                send_tick = True
                continue
        
        while len(self._instruction_complete_queue) > 0:
            (id, objective_complete) = self._instruction_complete_queue.popleft()
            self._handle_instruction_complete(id, objective_complete)
            send_tick = True

        # If the follower currently has no instructions, end their turn.
        if self._turn_state.turn == Role.FOLLOWER and not self.has_instructions_todo():
            self.update_turn(force_role_switch=True, end_reason="FollowerFinishedInstructions")
            send_tick = True

        selected_cards = list(self._map_provider.selected_cards())
        cards_changed = False
        if self._map_provider.selected_cards_collide() and not self._current_set_invalid:
            self._current_set_invalid = True
            cards_changed = True
            # Indicate invalid set.
            for card in selected_cards:
                # Outline the cards in red.
                card_select_action = CardSelectAction(card.id, True, Color(1, 0, 0, 1))
                self._map_provider.set_color(card.id, Color(1, 0, 0, 1))
                self.record_action(card_select_action)
        
        if not self._map_provider.selected_cards_collide() and self._current_set_invalid:
            logger.info("Marking set as clear (not invalid) because it is smaller than 3.")
            self._current_set_invalid = False
            cards_changed = True
            for card in selected_cards:
                # Outline the cards in blue.
                card_select_action = CardSelectAction(card.id, True, Color(0, 0, 1, 1))
                self._map_provider.set_color(card.id, Color(0, 0, 1, 1))
                self.record_action(card_select_action)

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
                self._turn_state.turn_number)
            self.send_turn_state(new_turn_state)
            self._game_recorder.record_card_set()
            # Add 3 new cards before clearing selected cards. This prevents
            # us from accidentally spawning cards in the same location as
            # the previous 3, which is confusing to the user.
            self._map_provider.add_random_unique_set()
            # Clear card state and remove the cards in the winning set.
            logger.info("Clearing selected cards")
            for card in selected_cards:
                self._map_provider.set_selected(card.id, False)
                actions = SetCompletionActions(card.id)
                for action in actions:
                    self.record_action(action)
                self._map_provider.remove_card(card.id)

        if cards_changed:
            # We've changed cards, so we need to mark the map as stale for all players.
            self._prop_update = self._map_provider.prop_update()
            self._send_state_machine_info = True
            for actor_id in self._actors:
                self._prop_stale[actor_id] = True

        # Check to see if the game is over.
        if self._turn_state.turns_left <= -1:
            logger.info(
                f"Game {self._room_id} is out of turns. Game over!")
            game_over_message = GameOverMessage(
                self._turn_state.game_start,
                self._turn_state.sets_collected,
                self._turn_state.score,
                self._turn_state.turn_number)
            self.send_turn_state(game_over_message)
            self.end_game()
            return

        
        # If any state transitions occured which prompt a tick, send one.
        if send_tick:
            self._iter = (self._iter + 1) % 2**32
            tick_message = StateMachineTick(iter=self._iter)
            for id in self._actors:
                self._ticks[id] = tick_message

    def on_game_over(self):
        self._game_recorder.record_game_over()
        if self._game_recorder.record() is not None:
            leaderboard.UpdateLeaderboard(self._game_recorder.record())
            experience.UpdateWorkerExperienceTable(self._game_recorder.record())
    
    def has_instructions_todo(self):
        for instruction in self._instructions:
            if not instruction.completed and not instruction.cancelled:
                return True
        return False

    def update_turn(self, force_role_switch=False, end_reason=""):
        opposite_role = Role.LEADER if self._turn_state.turn == Role.FOLLOWER else Role.FOLLOWER
        role_switch = (datetime.utcnow() >= self._turn_state.turn_end) or force_role_switch
        next_role = opposite_role if role_switch else self._turn_state.turn
        # Force the leader to act if there's no uncompleted instructions.
        turn_skipped = False
        if next_role == Role.FOLLOWER and not self.has_instructions_todo():
            next_role = Role.LEADER
            turn_skipped = True
        moves_remaining = max(self._turn_state.moves_remaining - 1, 0)
        turns_left = self._turn_state.turns_left
        turn_end = self._turn_state.turn_end
        turn_number = self._turn_state.turn_number
        if role_switch:
            # This is a mitigation to the invisible cards glitch. Update cards on role switches.
            self._prop_update = self._map_provider.prop_update()
            for actor_id in self._actors:
                self._prop_stale[actor_id] = True
            end_of_turn = (next_role == Role.LEADER)
            moves_remaining = self.moves_per_turn(next_role)
            turn_end = datetime.utcnow() + State.turn_duration(next_role)
            if end_of_turn:
                turns_left -= 1
                turn_number += 1
                self._game_recorder.record_end_of_turn(force_role_switch, end_reason, turn_skipped)

        turn_update = TurnUpdate(
            next_role,
            moves_remaining,
            turns_left,
            turn_end,
            self._turn_state.game_start,
            self._turn_state.sets_collected,
            self._turn_state.score,
            turn_number)
        self.send_turn_state(turn_update)

    def moves_per_turn(self, role):
        return LEADER_MOVES_PER_TURN if role == Role.LEADER else FOLLOWER_MOVES_PER_TURN
    
    def turn_state(self):
        return self._turn_state

    def calculate_score(self):
        self._turn_state.score = self._turn_state.sets_collected * 100
    
    def selected_cards(self):
        return list(self._map_provider.selected_cards())
        
    def check_for_stepped_on_cards(self, actor_id, action, color):
        actor = self._actors[actor_id]
        stepped_on_card = self._map_provider.card_by_location(actor.location())
        # If the actor just moved and stepped on a card, mark it as selected.
        if (action.action_type == ActionType.TRANSLATE) and (stepped_on_card is not None):
            logger.info(
                f"Player {actor.actor_id()} stepped on card {str(stepped_on_card)}.")
            selected = not stepped_on_card.selected
            self._map_provider.set_selected(stepped_on_card.id, selected)
            self._map_provider.set_color(stepped_on_card.id, color)
            card_select_action = CardSelectAction(stepped_on_card.id, selected, color)
            self.record_action(card_select_action)
            self._game_recorder.record_card_selection(stepped_on_card)
    
    def drain_messages(self, id, messages):
        for message in messages:
            self._drain_message(id, message)

    def _drain_message(self, id, message):
        if message.type == message_to_server.MessageType.ACTIONS:
            logger.info(f'Actions received. Room: {self._room_id}')
            self._drain_actions(id, message.actions)
        elif message.type == message_to_server.MessageType.OBJECTIVE:
            logger.info(
                f'Objective received. Room: {self._room_id}, Text: {message.objective.text}')
            self._drain_instruction(id, message.objective)
        elif message.type == message_to_server.MessageType.OBJECTIVE_COMPLETED:
            logger.info(
                f'Objective Compl received. Room: {self._room_id}, uuid: {message.objective_complete.uuid}')
            self._drain_instruction_complete(id, message.objective_complete)
            self._log_instructions()
        elif message.type == message_to_server.MessageType.TURN_COMPLETE:
            logger.info(f'Turn Complete received. Room: {self._room_id}')
            self._drain_turn_complete(id, message.turn_complete)
        elif message.type == message_to_server.MessageType.STATE_SYNC_REQUEST:
            logger.info(
                f'Sync request recvd. Room: {self._room_id}, Player: {id}')
            self.desync(id)
        elif message.type == message_to_server.MessageType.LIVE_FEEDBACK:
            logger.info(
                f'Live feedback recvd. Room: {self._room_id}, Player: {id}')
            self._drain_live_feedback(id, message.live_feedback)
        elif message.type == message_to_server.MessageType.CANCEL_PENDING_OBJECTIVES:
            logger.info(
                f'Cancel pending objectives recvd. Room: {self._room_id}, Player: {id}')
            self._drain_cancel_pending_instructions(id)
        else:
            logger.warn(f'Received unknown packet type: {message.type}')
    
    def _drain_actions(self, id, actions):
        for action in actions:
            logger.info(f'{action.id}:{action.displacement}')
            self._drain_action(id, action)

    def _drain_action(self, actor_id, action):
        if (action.id != actor_id):
            self.desync(actor_id)
            return
        self._actors[actor_id].add_action(action)

    def _drain_instruction(self, id, objective):
        if self._actors[id].role() != Role.LEADER:
            logger.warn(
                f'Warning, objective received from non-leader ID: {str(id)}')
            return
        if self._turn_state.turn != Role.LEADER:
            logger.warn(f'Warning, objective received out of turn.')
            return
        # TODO: Make UUID and non-UUID'd objectives separate message types.
        objective.uuid = uuid.uuid4().hex
        self._game_recorder.record_instruction(objective)
        self._instructions.append(objective)
        self._instruction_added = True
        for actor_id in self._actors:
            self._instructions_stale[actor_id] = True

    def _drain_instruction_complete(self, id, objective_complete):
        self._instruction_complete_queue.append((id, objective_complete))
    
    def _drain_live_feedback(self, id, feedback):
        if config.GlobalConfig() and not config.GlobalConfig().live_feedback_enabled:
            logger.info(f'Live feedback disabled. Dropping message.')
            return
        if feedback.signal == live_feedback.FeedbackType.NONE:
            logger.info(f'Received live feedback from {id} with type NONE. Dropping.')
            return
        if self._actors[id].role() != Role.LEADER:
            logger.warn(
                f'Warning, live feedback received from non-leader ID: {str(id)}')
            return
        if self._turn_state.turn != Role.FOLLOWER:
            logger.warn(f'Warning, live feedback received during the leader\'s turn.')
            return
        for actor_id in self._actors:
            self._live_feedback[actor_id] = feedback.signal
        # Find the follower.
        follower = None
        for actor_id in self._actors:
            if self._actors[actor_id].role() == Role.FOLLOWER:
                follower = self._actors[actor_id]
                break
        self._game_recorder.record_live_feedback(feedback, follower)
    
    def _drain_turn_complete(self, id, turn_complete):
        if self._actors[id].role() != self._turn_state.turn:
            logger.warn(
                f"Warning, turn complete received from ID: {str(id)} when it isn't their turn!")
            return
        if self._actors[id].role() == Role.LEADER:
            if not self.has_instructions_todo():
                logger.warn(f"Warning, turn complete received from leader ID: {str(id)} when there are no pending instructions!")
                return
        if len(self._turn_complete_queue) >= 1:
            logger.warn(
                f"Warning, turn complete queued from ID: {str(id)}, but one was already received!")
            return
        if self._actors[id].role() == Role.FOLLOWER and self.has_instructions_todo():
            logger.warn(f"Warning, turn complete received from ID: {str(id)} when there are pending instructions!")
            return
        self._turn_complete_queue.append((id, "UserPrompted"))
    
    def _drain_cancel_pending_instructions(self, id):
        logger.info(f"Cancel pending objectives received from ID: {str(id)}.")
        if self._actors[id].role() != Role.LEADER:
            logger.warn(
                f'Warning, objective cancellation from non-leader ID: {str(id)}')
            return
        if self._actors[id].role() == self._turn_state.turn:
            logger.warn(
                f'Warning, objective cancellation from leader ID: {str(id)} when it is their turn!')
            return
        # Queue up the cancellation.
        self._turn_complete_queue.append((id, "UserPromptedInterruption"))

    def cancel_pending_instructions(self):
        # Cancel all objectives.
        while len(self._instructions) > 0:
            instruction = self._instructions.popleft()
            instruction.cancelled = True
            self._instruction_history.append(instruction)

        for actor_id in self._actors:
            self._instructions_stale[actor_id] = True
        self._game_recorder.record_instruction_cancellation()

    def create_actor(self, role):
        if role in self._preloaded_actors:
            self._actors_added = True
            actor = self._preloaded_actors[role]
            del self._preloaded_actors[role]
            self._actors[actor.actor_id()] = actor
            self._action_history[actor.actor_id()] = []
            for actor_id in self._actors:
                self._prop_stale[actor_id] = True
            # Resend the latest turn state.
            self.resend_turn_state()
            self.mark_instructions_stale()
            # Mark clients as desynced.
            self.desync_all()
            return actor.actor_id()
        spawn_point = self._spawn_points.pop() if self._spawn_points else HecsCoord(0, 0, 0)
        asset_id = AssetId.PLAYER if role == Role.LEADER else AssetId.FOLLOWER_BOT
        actor = Actor(self._id_assigner.alloc(), asset_id, role, spawn_point, realtime=self._realtime_actions)
        self._actors[actor.actor_id()] = actor
        self._action_history[actor.actor_id()] = []
        # Resend the latest turn state.
        self.resend_turn_state()
        self.mark_instructions_stale()
        # Mark clients as desynced.
        self.desync_all()
        self._actors_added = True
        return actor.actor_id()
    
    def mark_instructions_stale(self):
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
        self._id_assigner.free(actor_id)
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
        self,
        player_id,
        out_messages: List[message_from_server.MessageFromServer]) -> bool:
        """ Serializes all messages to one player into a linear history. 
        
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
            objective_status_char = 'C' if objective.completed else 'I'
            if objective.cancelled:
                objective_status_char = 'X'
            logger.info(f'\t {objective_status_char} | {objective.text} | {objective.uuid}')
    
    def _next_message(self, player_id):
        actions = self._next_actions(player_id)
        if len(actions) > 0:
            logger.debug(
                f'Room {self._room_id} {len(actions)} actions for player_id {player_id}')
            msg = message_from_server.ActionsFromServer(actions)
            return msg

        map_update = self._next_map_update(player_id)
        if map_update is not None:
            logger.debug(
                f'Room {self._room_id} map update {map_update} for player_id {player_id}')
            return message_from_server.MapUpdateFromServer(map_update)
        
        prop_update = self._next_prop_update(player_id)
        if prop_update is not None:
            logger.debug(
                f'Room {self._room_id} prop update with {len(prop_update.props)} for player_id {player_id}')
            return message_from_server.PropUpdateFromServer(prop_update)

        if not self.is_synced(player_id):
            state_sync = self.sync_message_for_transmission(player_id)
            logger.debug(
                f'Room {self._room_id} state sync: {state_sync} for player_id {player_id}')
            logger.info(f"State sync with {player_id} and # {len(state_sync.actors)} actors")
            msg = message_from_server.StateSyncFromServer(state_sync)
            return msg

        objectives = self._next_instructions(player_id)
        if len(objectives) > 0:
            logger.debug(
                f'Room {self._room_id} {len(objectives)} texts for player_id {player_id}')
            msg = message_from_server.ObjectivesFromServer(objectives)
            return msg
        
        turn_state = self._next_turn_state(player_id)
        if not turn_state is None:
            logger.debug(
                f'Room {self._room_id} ts {turn_state} for player_id {player_id}')
            msg = message_from_server.GameStateFromServer(turn_state)
            return msg

        live_feedback = self._next_live_feedback(player_id)
        if not live_feedback is None:
            logger.info(
                f'Room {self._room_id} live feedback {live_feedback} for player_id {player_id}')
            msg = message_from_server.LiveFeedbackFromServer(live_feedback)
            return msg
        
        tick = self._next_tick(player_id)
        if not tick is None:
            logger.info(f'Room {self._room_id} tick {tick} for player_id {player_id}')
            msg = message_from_server.StateMachineTickFromServer(tick)
            return msg

        # Nothing to send.
        return None

    def _next_actions(self, actor_id):
        actor = self._actors[actor_id]
        if not actor_id in self._action_history:
            return []
        action_history = self._action_history[actor_id]

        if len(action_history) == 0:
            return []

        if actor.role() == Role.FOLLOWER:
            action_history = [CensorActionForFollower(action, actor) for action in action_history]

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

        all_instructions = list(self._instruction_history) + list(self._instructions)
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
            map_update = map_utils.CensorMapForFollower(map_update, self._actors[actor_id])
        
        self._game_recorder.record_map_update(map_update)

        # Send the latest map and mark as fresh for this player.
        self._map_stale[actor_id] = False
        return map_update
    
    def _next_prop_update(self, actor_id):
        if not actor_id in self._prop_stale:
            self._prop_stale[actor_id] = True
        
        if not self._prop_stale[actor_id]:
            return None
        
        prop_update = self._prop_update

        if self._actors[actor_id].role() == Role.FOLLOWER:
            prop_update = map_utils.CensorPropForFollower(prop_update, self._actors[actor_id])
        
        # Record the prop update to the database.
        self._game_recorder.record_prop_update(prop_update)

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
    def sync_message_for_transmission(self, actor_id):
        # This won't do... there might be some weird oscillation where an
        # in-flight invalid packet triggers another sync. need to communicate
        # round trip.
        sync_message = self.state(actor_id)
        self._synced[actor_id] = True
        return sync_message

    def valid_action(self, actor_id, action):
        if (action.action_type == ActionType.TRANSLATE):
            cartesian = action.displacement.cartesian()
            # Add a small delta for floating point comparison.
            if (math.sqrt(cartesian[0]**2 + cartesian[1]**2) > 1.001):
                logger.info(f"Invalid action: translation too large {action}")
                return False
            destination = HecsCoord.add(self._actors[actor_id].location(), action.displacement)
            if self._map_provider.edge_between(self._actors[actor_id].location(), destination):
                logger.info(f"Invalid action: attempts to move through wall {action}")
                return False
            forward_location = (self._actors[actor_id]
                            .location()
                            .neighbor_at_heading(self._actors[actor_id].heading_degrees()))
            backward_location = (self._actors[actor_id]
                            .location()
                            .neighbor_at_heading(self._actors[actor_id].heading_degrees() + 180))
            if destination not in [forward_location, backward_location]:
                logger.info(f"Invalid action: attempts to move to {destination.to_offset_coordinates()} which is invalid. Facing: {self._actors[actor_id].heading_degrees()} backward location: {backward_location.to_offset_coordinates()}. exp: {action.expiration}")
                return False
        if (action.action_type == ActionType.ROTATE):
            if (abs(action.rotation) > 60.01):
                logger.info(f"Invalid action: attempts to rotate too much {action}")
                return False
        return True

    def _handle_instruction_complete(self, id, objective_complete):
        if self._actors[id].role() != Role.FOLLOWER:
            logger.warn(
                f'Warning, obj complete received from non-follower ID: {str(id)}')
            return
        if len(self._instructions) == 0:
            logger.warn(
                f'Warning, obj complete received with no instructions ID: {str(id)}')
            return
        if self._instructions[0].uuid != objective_complete.uuid:
            logger.warn(
                f'Warning, obj complete received with wrong uuid ID: {objective_complete.uuid}')
            return
        if self._instructions[0].cancelled:
            logger.warn(
                f'Warning, obj complete received for cancelled objective ID: {objective_complete.uuid}')
            return
        active_instruction = self._instructions.popleft()
        active_instruction.completed = True
        self._instruction_history.append(active_instruction)
        for actor_id in self._actors:
            self._instructions_stale[actor_id] = True
        self._game_recorder.record_instruction_complete(objective_complete)