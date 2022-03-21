from actor import Actor
from assets import AssetId
from messages.action import Action, Color, ActionType, CensorActionForFollower
from messages.rooms import Role
from messages import live_feedback, message_from_server
from messages import message_to_server
from messages import objective, state_sync
from hex import HecsCoord
from queue import Queue
from map_provider import MapProvider, MapType
from card import CardSelectAction, SetCompletionActions
from util import IdAssigner
from datetime import datetime, timedelta
from messages.turn_state import TurnState, GameOverMessage, TurnUpdate
import leaderboard


import aiohttp
import asyncio
import dataclasses
import logging
import math
import random
import time
import uuid

import schemas.game
import schemas.map
import schemas.cards
import schemas.leaderboard
import map_utils

LEADER_MOVES_PER_TURN = 5
FOLLOWER_MOVES_PER_TURN = 10

logger = logging.getLogger()

class State(object):
    def __init__(self, room_id, game_record):
        self._room_id = room_id
        self._id_assigner = IdAssigner()

        # Create an entry in the Game database table.
        self._game_record = game_record
        self._game_record.world_seed = repr(random.getstate())
        self._game_record.score = 0
        self._game_record.valid = True
        self._game_record.who_is_agent = ""

        self._last_move = None

        # Logging init.
        self._recvd_log = logging.getLogger(f'room_{room_id}.recv')
        self._record_log = logging.getLogger(f'room_{room_id}.log')
        self._sent_log = logging.getLogger(f'room_{room_id}.sent')
        self._recvd_log.info("State created.")
        self._record_log.info("State created.")
        self._sent_log.info("State created.")

        # Maps from actor_id (prop id) to actor object (see definition below).
        self._actors = {}

        # Map props and actors share IDs from the same pool, so the ID assigner
        # is shared to prevent overlap.
        self._map_provider = MapProvider(MapType.RANDOM, self._id_assigner)
        self._game_record.number_cards = len(self._map_provider.cards())
        
        self._objectives = []
        self._objectives_stale = {}  # Maps from player_id -> bool if their objective list is stale.
        self._active_objective = None

        self._map_update = self._map_provider.map()
        self._map_stale = {} # Maps from player_id -> bool if their map is stale.
        self._map_update_count = 0

        self._live_feedback = {} # Maps from player_id -> live_feedback.FeedbackType if live feedback is pending. Otherwise live_feedback.FeedbackType.None.

        self._synced = {}
        self._action_history = {}
        self._last_tick = datetime.now() # Used to time 1s ticks for turn state updates.
        initial_turn = TurnUpdate(
            Role.LEADER, LEADER_MOVES_PER_TURN, 6,
            datetime.now() + self.turn_duration(Role.LEADER),
            datetime.now(), 0, 0, 0)
        self._turn_history = {}
        self.record_turn_state(initial_turn)

        self._game_record.save()
        for card in self._map_provider.cards():
            card_record = self.get_or_create_card_record(card)
            card_record.save()

        self._spawn_points = self._map_provider.spawn_points()
        random.shuffle(self._spawn_points)
        self._done = False
        self._game_record.save()

    def turn_duration(self, role):
        return timedelta(seconds=60) if role == Role.LEADER else timedelta(seconds=45)

    def record_turn_state(self, turn_state):
        # Record a copy of the current turn state.
        self._record_log.debug(turn_state)
        self._turn_state = turn_state
        for actor_id in self._actors:
            if not actor_id in self._turn_history:
                self._turn_history[actor_id] = Queue()
            self._turn_history[actor_id].put(
                dataclasses.replace(turn_state))

    def drain_turn_state(self, actor_id):
        if not actor_id in self._turn_history:
            self._turn_history[actor_id] = Queue()
        if self._turn_history[actor_id].empty():
            return None
        turn = self._turn_history[actor_id].get()
        self._sent_log.debug(f"to: {actor_id} turn_state: {turn}")
        return turn

    def end_game(self):
        logging.info(f"Game ending.")
        self._done = True

    def record_action(self, action):
        # Marks an action as validated (i.e. it did not conflict with other actions).
        # Queues this action to be sent to each user.
        self._record_log.info(action)
        for id in self._actors:
            actor = self._actors[id]
            self._action_history[actor.actor_id()].append(action)

    def map(self):
        return self._map_provider.map()

    def cards(self):
        self._map_provider.cards()
    
    def done(self):
        return self._done

    async def update(self):
        last_loop = time.time()
        current_set_invalid = False
        while not self._done:
            await asyncio.sleep(0.001)
            poll_period = time.time() - last_loop
            if (poll_period) > 0.1:
                logging.warn(
                    f"Game {self._room_id} slow poll period of {poll_period}s")
            last_loop = time.time()

            # Check to see if the game is out of time.
            if self._turn_state.turns_left <= -1:
                logging.info(
                    f"Game {self._room_id} is out of turns. Game over!")
                game_over_message = GameOverMessage(
                    self._turn_state.game_start,
                    self._turn_state.sets_collected,
                    self._turn_state.score,
                    self._turn_state.turn_number)
                self.record_turn_state(game_over_message)
                self._game_record.completed = True
                self._game_record.end_time = datetime.now()
                self._game_record.score = self._turn_state.score
                self._game_record.save()
                self.end_game()
                continue

            # Recalculate the turn state with the remaining game time.
            if datetime.now() > self._last_tick + timedelta(milliseconds=1000):
                self._last_tick = datetime.now()
                turn_update = TurnUpdate(self._turn_state.turn,
                                         self._turn_state.moves_remaining,
                                         self._turn_state.turns_left,
                                         self._turn_state.turn_end,
                                         self._turn_state.game_start,
                                         self._turn_state.sets_collected,
                                         self._turn_state.score,
                                         self._turn_state.turn_number)
                self.record_turn_state(turn_update)
            
            if datetime.now() >= self._turn_state.turn_end:
                self.update_turn()

            # If the follower currently has no instructions, end their turn.
            if self._turn_state.turn == Role.FOLLOWER and not self.has_instructions_todo():
                self.update_turn(force_role_switch=True, end_reason="FollowerFinishedInstructions")

            if self._turn_state.turn == Role.FOLLOWER and self._turn_state.moves_remaining <= 0:
                self.update_turn(force_role_switch=True, end_reason="FollowerOutOfMoves")

            # Handle actor actions.
            for actor_id in self._actors:
                actor = self._actors[actor_id]
                if actor.has_actions():
                    logger.info(f"Actor {actor_id} has pending actions.")
                    proposed_action = actor.peek()
                    if not self._turn_state.turn == actor.role():
                        actor.drop()
                        self.desync(actor_id)
                        logger.info(
                            f"Actor {actor_id} is not the current role. Dropping pending action.")
                        continue
                    if self._turn_state.moves_remaining == 0:
                        actor.drop()
                        self.desync(actor_id)
                        logger.info(
                            f"Actor {actor_id} is out of moves. Dropping pending action.")
                        continue
                    if self.valid_action(actor_id, proposed_action):
                        self.record_move(actor, proposed_action)
                        actor.step()
                        self.record_action(proposed_action)
                        color = Color(0, 0, 1, 1) if not current_set_invalid else Color(1, 0, 0, 1)
                        self.check_for_stepped_on_cards(actor_id, proposed_action, color)
                        self.update_turn()
                    else:
                        actor.drop()
                        self.desync(actor_id)
                        self._record_log.error(f"Resyncing {actor_id} after invalid action.")
                        continue

            selected_cards = list(self._map_provider.selected_cards())
            cards_changed = False
            if self._map_provider.selected_cards_collide() and not current_set_invalid:
                current_set_invalid = True
                self._record_log.info("Invalid set detected.")
                cards_changed = True
                # Indicate invalid set.
                for card in selected_cards:
                    # Outline the cards in red.
                    card_select_action = CardSelectAction(card.id, True, Color(1, 0, 0, 1))
                    self._map_provider.set_color(card.id, Color(1, 0, 0, 1))
                    self.record_action(card_select_action)
            
            if not self._map_provider.selected_cards_collide() and current_set_invalid:
                logger.info("Marking set as clear (not invalid) because it is smaller than 3.")
                current_set_invalid = False
                cards_changed = True
                for card in selected_cards:
                    # Outline the cards in blue.
                    card_select_action = CardSelectAction(card.id, True, Color(0, 0, 1, 1))
                    self._map_provider.set_color(card.id, Color(0, 0, 1, 1))
                    self.record_action(card_select_action)

            if self._map_provider.selected_valid_set():
                self._record_log.info("Unique set collected. Awarding points.")
                current_set_invalid = False
                added_turns = 0
                cards_changed = True
                if self._turn_state.sets_collected == 0:
                    added_turns = 5
                elif self._turn_state.sets_collected in [1, 2]:
                    added_turns = 4
                elif self._turn_state.sets_collected in [3, 4]:
                    added_turns = 3
                elif self._turn_state.sets_collected in [5, 6]:
                    added_turns = 2
                elif self._turn_state.sets_collected in [7, 8]:
                    added_turns = 1
                new_turn_state = TurnUpdate(
                    self._turn_state.turn,
                    self._turn_state.moves_remaining,
                    self._turn_state.turns_left + added_turns,
                    self._turn_state.turn_end,
                    self._turn_state.game_start,
                    self._turn_state.sets_collected + 1,
                    self._turn_state.score + 1,
                    self._turn_state.turn_number)
                self.record_turn_state(new_turn_state)
                set_record = schemas.cards.CardSets()
                set_record.game = self._game_record
                set_record.move = self._last_move
                set_record.score = new_turn_state.score
                set_record.save()
                for card in selected_cards: 
                    card_record = self.get_or_create_card_record(card)
                    card_record.set = set_record
                    card_record.save()
                self._game_record.score = new_turn_state.score
                self._game_record.save()
                # Add 3 new cards before clearing selected cards. This prevents
                # us from accidentally spawning cards in the same location as
                # the previous 3, which is confusing to the user.
                self._map_provider.add_random_unique_set()
                # Clear card state and remove the cards in the winning set.
                logging.info("Clearing selected cards")
                for card in selected_cards:
                    self._map_provider.set_selected(card.id, False)
                    actions = SetCompletionActions(card.id)
                    for action in actions:
                        self.record_action(action)
                    self._map_provider.remove_card(card.id)

            if cards_changed:
                # We've changed cards, so we need to mark the map as stale for all players.
                self._map_update = self._map_provider.map()
                for actor_id in self._actors:
                    self._map_stale[actor_id] = True
        # Make sure to mark the game's end time.
        self._game_record.end_time = datetime.now()
        self._game_record.save()
        leaderboard.UpdateLeaderboard(self._game_record)
    
    def record_objective(self, objective):
        instruction = schemas.game.Instruction()
        instruction.game = self._game_record
        instruction.worker = self._game_record.leader
        instruction.uuid = objective.uuid
        instruction.text = objective.text
        instruction.instruction_number = len(self._objectives) + 1
        instruction.turn_issued = self._turn_state.turn_number
        instruction.save()

    def record_move(self, actor, proposed_action: Action):
        move = schemas.game.Move()
        move.game = self._game_record
        if actor.role() == Role.FOLLOWER:
            if self._active_objective is not None:
                last_obj_record = schemas.game.Instruction.select().where(
                    schemas.game.Instruction.uuid == self._active_objective.uuid).get()
                move.instruction = last_obj_record
        move.character_role = actor.role()
        if actor.role == Role.LEADER:
            print(self._tutorial_record.leader.hashed_id)
            move.worker = self._tutorial_record.leader
        if actor.role == Role.FOLLOWER:
            print(self._tutorial_record.leader.hashed_id)
            move.worker = self._tutorial_record.follower
        move.action = proposed_action
        move.position_before = actor.location()
        move.orientation_before = actor.heading_degrees()
        move.turn_number = self._turn_state.turn_number
        move.game_time = datetime.now() - self._game_record.start_time
        move.server_time = datetime.now()
        move_code = ""
        forward_location = actor.location().neighbor_at_heading(actor.heading_degrees())
        backward_location = actor.location().neighbor_at_heading(actor.heading_degrees() + 180)
        new_location = HecsCoord.add(actor.location(), proposed_action.displacement)
        if new_location == forward_location:
            move_code = "MF"
        elif new_location == backward_location:
            move_code = "MB"
        elif new_location == actor.location():
            if proposed_action.rotation == 60:
                move_code = "TR"
            elif proposed_action.rotation == -60:
                move_code = "TL"
            else:
                move_code = "INVALID"
        else:
            move_code = "INVALID"
        move.action_code = move_code
        logger.info(f"========== MOVE CODE: {move_code}")
        self._last_move = move
        move.save()

    def has_instructions_todo(self):
        for objective in self._objectives:
            if not objective.completed:
                return True
        return False

    def update_turn(self, force_role_switch=False, end_reason=""):
        opposite_role = Role.LEADER if self._turn_state.turn == Role.FOLLOWER else Role.FOLLOWER
        role_switch = (datetime.now() >= self._turn_state.turn_end) or force_role_switch
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
            end_of_turn = (next_role == Role.LEADER)
            moves_remaining = self.moves_per_turn(next_role)
            turn_end = datetime.now() + self.turn_duration(next_role)
            if end_of_turn:
                turns_left -= 1
                turn_number += 1

                # Record the turn end to DB.
                self._game_record.number_turns = self._turn_state.turn_number + 1
                self._game_record.save()

                turn = schemas.game.Turn()
                turn.game = self._game_record
                # Due to a change in how turns are counted, each turn now
                # includes movements for both roles. This field is now deprecated.
                turn.role = ""
                turn.turn_number = self._turn_state.turn_number  # Recording the turn that just ended.
                end_method = end_reason if force_role_switch else "RanOutOfTime"
                turn.end_method = end_method
                notes = []
                if turn_skipped:
                    notes.append("SkippedTurnNoInstructionsTodo")
                if self._turn_state.moves_remaining <= 0:
                    notes.append("UsedAllMoves")
                if self._turn_state.turn == Role.FOLLOWER and not self.has_instructions_todo():
                    notes.append("FinishedAllCommands")
                turn.notes = ",".join(notes)
                turn.save()

        turn_update = TurnUpdate(
            next_role,
            moves_remaining,
            turns_left,
            turn_end,
            self._turn_state.game_start,
            self._turn_state.sets_collected,
            self._turn_state.score,
            turn_number)
        self.record_turn_state(turn_update)

    def moves_per_turn(self, role):
        return LEADER_MOVES_PER_TURN if role == Role.LEADER else FOLLOWER_MOVES_PER_TURN
    
    def turn_state(self):
        return self._turn_state

    def calculate_score(self):
        self._turn_state.score = self._turn_state.sets_collected * 100
    
    def selected_cards(self):
        return list(self._map_provider.selected_cards())
    
    def get_or_create_card_record(self, card):
        record, created = schemas.cards.Card.get_or_create(game=self._game_record, count=card.count,color=str(card.color),shape=str(card.shape),
                                                location=card.location, defaults={'turn_created': self._turn_state.turn_number})
        return record
        
    def check_for_stepped_on_cards(self, actor_id, action, color):
        actor = self._actors[actor_id]
        stepped_on_card = self._map_provider.card_by_location(
            actor.location())
        # If the actor just moved and stepped on a card, mark it as selected.
        if (action.action_type == ActionType.TRANSLATE) and (stepped_on_card is not None):
            logger.info(
                f"Player {actor.actor_id()} stepped on card {str(stepped_on_card)}.")
            selected = not stepped_on_card.selected
            self._map_provider.set_selected(stepped_on_card.id, selected)
            self._map_provider.set_color(stepped_on_card.id, color)
            card_select_action = CardSelectAction(stepped_on_card.id, selected, color)
            self.record_action(card_select_action)
            selection_record = schemas.cards.CardSelections()
            selection_record.game = self._game_record
            selection_record.move = self._last_move
            selection_record.type = "select" if selected else "unselect"
            card_record = self.get_or_create_card_record(stepped_on_card)
            selection_record.card = card_record
            selection_record.save()

    def handle_packet(self, id, message):
        if message.type == message_to_server.MessageType.ACTIONS:
            logger.info(f'Actions received. Room: {self._room_id}')
            for action in message.actions:
                logger.info(f'{action.id}:{action.displacement}')
                self.handle_action(id, action)
        elif message.type == message_to_server.MessageType.OBJECTIVE:
            logger.info(
                f'Objective received. Room: {self._room_id}, Text: {message.objective.text}')
            self.handle_objective(id, message.objective)
        elif message.type == message_to_server.MessageType.OBJECTIVE_COMPLETED:
            logger.info(
                f'Objective Compl received. Room: {self._room_id}, Text: {message.objective_complete.uuid}')
            self.handle_objective_complete(id, message.objective_complete)
        elif message.type == message_to_server.MessageType.TURN_COMPLETE:
            logger.info(f'Turn Complete received. Room: {self._room_id}')
            self.handle_turn_complete(id, message.turn_complete)
        elif message.type == message_to_server.MessageType.STATE_SYNC_REQUEST:
            logger.info(
                f'Sync request recvd. Room: {self._room_id}, Player: {id}')
            self.desync(id)
        elif message.type == message_to_server.MessageType.LIVE_FEEDBACK:
            logger.info(
                f'Live feedback recvd. Room: {self._room_id}, Player: {id}')
            self.handle_live_feedback(id, message.live_feedback)
        else:
            logger.warn(f'Received unknown packet type: {message.type}')

    def handle_action(self, actor_id, action):
        if (action.id != actor_id):
            self.desync(actor_id)
            return
        self._recvd_log.info(action)
        self._actors[actor_id].add_action(action)

    def handle_objective(self, id, objective):
        if self._actors[id].role() != Role.LEADER:
            logger.warn(
                f'Warning, objective received from non-leader ID: {str(id)}')
            return
        # TODO: Make UUID and non-UUID'd objectives separate message types.
        objective.uuid = uuid.uuid4().hex
        self.record_objective(objective)
        self._recvd_log.info(objective)
        self._objectives.append(objective)
        if self._active_objective is None:
            self._active_objective = objective
        for actor_id in self._actors:
            self._objectives_stale[actor_id] = True

    def handle_objective_complete(self, id, objective_complete):
        if self._actors[id].role() != Role.FOLLOWER:
            logger.warn(
                f'Warning, obj complete received from non-follower ID: {str(id)}')
            return
        self._recvd_log.info(objective_complete)
        for i, objective in enumerate(self._objectives):
            if objective.uuid == objective_complete.uuid:
                self._record_log.info(objective_complete)
                self._objectives[i].completed = True
                break
        # Mark the next "active" objective.
        if i < len(self._objectives) - 1:
            self._active_objective = self._objectives[i + 1]
        else:
            self._active_objective = None
        for actor_id in self._actors:
            self._objectives_stale[actor_id] = True
        instruction = schemas.game.Instruction.select().where(
            schemas.game.Instruction.uuid==objective_complete.uuid).get()
        instruction.turn_completed = self._turn_state.turn_number
        instruction.save()
    
    def handle_live_feedback(self, id, feedback):
        if feedback.signal == live_feedback.FeedbackType.NONE:
            logger.info(f'Received live feedback from {id} with type NONE. Dropping.')
            return
        for actor_id in self._actors:
            if actor_id == id:
                continue
            self._live_feedback[actor_id] = feedback.signal
        
        # Find the follower.
        follower = None
        for actor_id in self._actors:
            if self._actors[actor_id].role() == Role.FOLLOWER:
                follower = self._actors[actor_id]
                break
        
        # Create database record of the live feedback.
        live_feedback_record = schemas.game.LiveFeedback()
        live_feedback_record.game = self._game_record
        live_feedback_record.feedback_type = "POSITIVE" if feedback.signal == live_feedback.FeedbackType.POSITIVE else "NEGATIVE"
        
        # Update the follower's state.
        if self._active_objective is not None:
            last_obj_record = schemas.game.Instruction.select().where(
                schemas.game.Instruction.uuid == self._active_objective.uuid).get()
            live_feedback_record.instruction = last_obj_record
        live_feedback_record.turn_number = self._turn_state.turn_number
        if follower is not None:
            live_feedback_record.follower_position = follower.location()
            live_feedback_record.follower_orientation = follower.heading_degrees()
        live_feedback_record.game_time = datetime.now() - self._game_record.start_time
        live_feedback_record.server_time = datetime.now()
        live_feedback_record.save()
    
    def handle_turn_complete(self, id, turn_complete):
        if self._actors[id].role() != self._turn_state.turn:
            logger.warn(
                f"Warning, turn complete received from ID: {str(id)} when it isn't their turn!")
            return
        if self._actors[id].role() == Role.LEADER:
            if not self.has_instructions_todo():
                logger.warn(f"Warning, turn complete received from ID: {str(id)} when it isn't their turn!")
                return
        self._recvd_log.info(f"player_id: {id} turn_complete received.")
        self.update_turn(force_role_switch=True, end_reason="UserPrompted")

    def create_actor(self, role):
        spawn_point = self._spawn_points.pop() if self._spawn_points else HecsCoord(0, 0, 0)
        asset_id = AssetId.PLAYER if role == Role.LEADER else AssetId.FOLLOWER_BOT
        actor = Actor(self._id_assigner.alloc(), asset_id, role, spawn_point)
        self._actors[actor.actor_id()] = actor
        self._action_history[actor.actor_id()] = []
        self._synced[actor.actor_id()] = False
        # Mark clients as desynced.
        self.desync_all()
        return actor.actor_id()

    def free_actor(self, actor_id):
        if actor_id in self._actors:
            del self._actors[actor_id]
        if actor_id in self._action_history:
            del self._action_history[actor_id]
        if actor_id in self._objectives_stale:
            del self._objectives_stale[actor_id]
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
            if self._objectives_stale[actor_id]:
                return True
            if not self._turn_history[actor_id].empty():
                return True
        return False

    def drain_message(self, player_id):
        """ Returns a MessageFromServer object to send to the indicated player.

            If no message is available, returns None.
        """
        actions = self.drain_actions(player_id)
        if len(actions) > 0:
            logger.debug(
                f'Room {self._room_id} drained {len(actions)} actions for player_id {player_id}')
            msg = message_from_server.ActionsFromServer(actions)
            return msg

        map_update = self.drain_map_update(player_id)
        if map_update is not None:
            logger.debug(
                f'Room {self._room_id} drained map update {map_update} for player_id {player_id}')
            return message_from_server.MapUpdateFromServer(map_update)

        if not self.is_synced(player_id):
            state_sync = self.sync_message_for_transmission(player_id)
            logger.debug(
                f'Room {self._room_id} drained state sync: {state_sync} for player_id {player_id}')
            msg = message_from_server.StateSyncFromServer(state_sync)
            return msg

        objectives = self.drain_objectives(player_id)
        if len(objectives) > 0:
            logger.debug(
                f'Room {self._room_id} drained {len(objectives)} texts for player_id {player_id}')
            msg = message_from_server.ObjectivesFromServer(objectives)
            return msg
        
        turn_state = self.drain_turn_state(player_id)
        if not turn_state is None:
            logger.debug(
                f'Room {self._room_id} drained ts {turn_state} for player_id {player_id}')
            msg = message_from_server.GameStateFromServer(turn_state)
            return msg

        live_feedback = self.drain_live_feedback(player_id)
        if not live_feedback is None:
            logger.info(
                f'Room {self._room_id} drained live feedback {live_feedback} for player_id {player_id}')
            msg = message_from_server.LiveFeedbackFromServer(live_feedback)
            return msg

        # Nothing to send.
        return None

    def drain_actions(self, actor_id):
        actor = self._actors[actor_id]
        if not actor_id in self._action_history:
            return []
        action_history = self._action_history[actor_id]

        if len(action_history) == 0:
            return []

        if actor.role() == Role.FOLLOWER:
            action_history = [CensorActionForFollower(action, actor) for action in action_history]

        # Log actions sent to client.
        for action in action_history:
            self._sent_log.debug(f"to: {actor_id} action: {action}")
        self._action_history[actor_id] = []
        return action_history

    def drain_objectives(self, actor_id):
        if not actor_id in self._objectives_stale:
            self._objectives_stale[actor_id] = True
        
        if not self._objectives_stale[actor_id]:
            return []
        
        # Send the latest objective list and mark as fresh for this player.
        self._objectives_stale[actor_id] = False
        self._sent_log.info(f"to: {actor_id} objectives: {self._objectives}")
        return self._objectives
    
    def drain_map_update(self, actor_id):
        if not actor_id in self._map_stale:
            self._map_stale[actor_id] = True
        
        if not self._map_stale[actor_id]:
            return None
        
        self._map_update_count += 1

        map_update = self._map_update

        if self._actors[actor_id].role() == Role.FOLLOWER:
            map_update = map_utils.CensorMapForFollower(map_update, self._actors[actor_id])
        
        # Record the map update to the database.
        map_record = schemas.map.MapUpdate()
        map_record.world_seed = self._game_record.world_seed
        map_record.map_data = map_update
        map_record.game = self._game_record
        map_record.map_update_number = self._map_update_count
        map_record.save()

        # Send the latest map and mark as fresh for this player.
        self._map_stale[actor_id] = False
        self._sent_log.debug(f"to: {actor_id} map: {map_update}")
        return map_update

    def drain_live_feedback(self, actor_id):
        if actor_id not in self._live_feedback:
            return None
        if self._live_feedback[actor_id] == live_feedback.FeedbackType.NONE:
            return None
        feedback = live_feedback.LiveFeedbackFromType(self._live_feedback[actor_id])
        self._live_feedback[actor_id] = live_feedback.FeedbackType.NONE
        return feedback



    # Returns the current state of the game.
    def state(self, actor_id=-1):
        actor_states = []
        for a in self._actors:
            actor = self._actors[a]
            actor_states.append(actor.state())
        return state_sync.StateSync(len(self._actors), actor_states, actor_id)

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
                return False
        if (action.action_type == ActionType.ROTATE):
            if (action.rotation > 60.01):
                return False
        return True


class Actor(object):
    def __init__(self, actor_id, asset_id, role, spawn):
        self._actor_id = actor_id
        self._asset_id = asset_id
        self._actions = Queue()
        self._location = spawn
        self._heading_degrees = 0
        self._role = role

    def turn():
        pass

    def actor_id(self):
        return self._actor_id

    def asset_id(self):
        return self._asset_id

    def role(self):
        return self._role

    def add_action(self, action):
        self._actions.put(action)

    def has_actions(self):
        return not self._actions.empty()

    def location(self):
        return self._location

    def heading_degrees(self):
        return int(self._heading_degrees)

    def state(self):
        return state_sync.Actor(self.actor_id(), self.asset_id(),
                                self._location, self._heading_degrees)

    def peek(self):
        """ Peeks at the next action without consuming it. """
        return self._actions.queue[0]

    def step(self):
        """ Executes & consumes an action from the queue."""
        if not self.has_actions():
            return
        action = self._actions.get()
        self._location = HecsCoord.add(self._location, action.displacement)
        self._heading_degrees += action.rotation

    def drop(self):
        """ Drops an action instead of acting upon it."""
        if not self.has_actions():
            return
        _ = self._actions.get()
