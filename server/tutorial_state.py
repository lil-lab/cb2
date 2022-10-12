from server.actor import Actor
from server.assets import AssetId
from server.messages.action import Action, Color, ActionType, CensorActionForFollower, Delay
from server.messages.rooms import Role
from server.messages import message_from_server
from server.messages import message_to_server
from server.messages import state_sync
from server.messages.state_sync import StateMachineTick
from server.messages.objective import ObjectiveMessage, ObjectiveCompleteMessage
from server.hex import HecsCoord
from server.map_provider import MapProvider, MapType
from server.card import CardSelectAction, SetCompletionActions
from server.util import IdAssigner
from server.messages.turn_state import TurnState, GameOverMessage, TurnUpdate
from server.messages.tutorials import FollowerActions, TutorialRequestType, TutorialResponseFromStep, TutorialCompletedResponse, RoleFromTutorialName, TooltipType
from server.tutorial_steps import LoadTutorialSteps

from datetime import datetime, timedelta

from multiprocessing import dummy
from async_timeout import current_task
from numpy import select
from queue import Queue
from typing import List

import aiohttp
import asyncio
import dataclasses
import logging
import math
import random
import time
import uuid

import server.map_utils as map_utils
import server.schemas.game as game_db
import server.schemas.map as map_db
import server.schemas.cards as cards_db
import server.schemas.prop as prop_db

LEADER_MOVES_PER_TURN = -1
FOLLOWER_MOVES_PER_TURN = -1

logger = logging.getLogger()

class TutorialGameState(object):
    def __init__(self, room_id, tutorial_name, tutorial_record):
        self._room_id = room_id

        self._player_role = RoleFromTutorialName(tutorial_name)

        self._tutorial_record = tutorial_record
        self._tutorial_record.world_seed = repr(random.getstate())
        self._tutorial_record.score = 0
        self._tutorial_record.valid = True
        self._tutorial_record.who_is_agent = ""

        self._last_move = None

        # Logging init.
        self._recvd_log = logging.getLogger(f'room_{room_id}.recv')
        self._record_log = logging.getLogger(f'room_{room_id}.log')
        self._sent_log = logging.getLogger(f'room_{room_id}.sent')
        self._recvd_log.info("Tutorial State created.")
        self._record_log.info("Tutorial State created.")
        self._sent_log.info("Tutorial State created.")

        self._tutorial_name = tutorial_name
        self._tutorial_steps = LoadTutorialSteps(tutorial_name)
        self._tutorial_step_index = 0
        self._tutorial_responses = Queue()

        self._turn_complete_queue = []

        self._step_indicators = set()

        # Maps from actor_id (prop id) to actor object (see definition below).
        self._actors = {}

        self._iter = 0

        # Map props and actors share IDs from the same pool, so the ID assigner
        # is shared to prevent overlap.
        self._map_provider = MapProvider(MapType.HARDCODED)
        self._id_assigner = self._map_provider.id_assigner()  # Map and state props share same ID space.
        self._tutorial_record.number_cards = len(self._map_provider.cards())

        self._current_set_invalid = False
        
        self._objectives = []
        self._objectives_stale = {}  # Maps from player_id -> bool if their objective list is stale.

        self._map_update = self._map_provider.map()
        self._map_stale = {} # Maps from player_id -> bool if their map is stale.
        self._map_update_count = 0

        self._prop_update = self._map_provider.prop_update() # Maps from player_id -> list of props to update.
        self._prop_stale = {} # Maps from player_id -> bool if their prop list is stale.

        self._synced = {}
        self._action_history = {}
        self._last_tick = datetime.now() # Used to time 1s ticks for turn state updates.
        initial_turn = TurnUpdate(
            self._player_role, LEADER_MOVES_PER_TURN, 6,
            datetime.now() + self.turn_duration(self._player_role),
            datetime.now(), 0, 0, 0)
        self._turn_history = {}
        self.record_turn_state(initial_turn)

        self._tutorial_record.save()
        for card in self._map_provider.cards():
            card_record = self.get_or_create_card_record(card)
            card_record.save()

        self._spawn_points = [HecsCoord(1, 1, 0), HecsCoord(1, 2, 2)]
        self._done = False

        if (self._player_role == Role.LEADER):
            dummy_character_id = self.create_actor(Role.FOLLOWER, True)
            self._dummy_character = self._actors[dummy_character_id]
        elif (self._player_role == Role.FOLLOWER):
            dummy_character_id = self.create_actor(Role.LEADER, True)
            self._dummy_character = self._actors[dummy_character_id]

    def player_ids(self):
        return self._actors.keys()

    def turn_duration(self, role):
        return timedelta(seconds=60) if role == Role.LEADER else timedelta(seconds=45)

    def record_turn_state(self, turn_state):
        # Record a copy of the current turn state.
        self._record_log.info(turn_state)
        self._turn_state = turn_state
        for actor_id in self._actors:
            if not actor_id in self._turn_history:
                self._turn_history[actor_id] = Queue()
            self._turn_history[actor_id].put(
                dataclasses.replace(turn_state))

    def _next_turn_state(self, actor_id):
        if not actor_id in self._turn_history:
            self._turn_history[actor_id] = Queue()
        if self._turn_history[actor_id].empty():
            return None
        turn = self._turn_history[actor_id].get()
        self._sent_log.info(f"to: {actor_id} turn_state: {turn}")
        return turn

    def end_game(self):
        logging.info(f"Game ending.")
        self.free_actor(self._dummy_character.actor_id())
        self._done = True

    def record_action(self, action):
        # Marks an action as validated (i.e. it did not conflict with other actions).
        # Queues this action to be sent to each user.
        self._record_log.info(action)
        for id in self._actors:
            actor = self._actors[id]
            self._action_history[actor.actor_id()].append(action)
    
    def record_objective(self, objective):
        instruction = game_db.Instruction()
        instruction.game = self._tutorial_record
        instruction.worker = self._tutorial_record.leader
        instruction.uuid = objective.uuid
        instruction.text = objective.text
        instruction.instruction_number = len(self._objectives) + 1
        instruction.turn_issued = self._turn_state.turn_number
        instruction.save()

    def record_move(self, actor, proposed_action):
        move = game_db.Move()
        move.game = self._tutorial_record
        if actor.role() == Role.FOLLOWER:
            last_objective = None
            for objective in self._objectives:
                if not objective.completed:
                    last_objective = objective
            if last_objective is not None:
                last_obj_record = game_db.Instruction.select().where(
                    game_db.Instruction.uuid == last_objective.uuid).get()
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
        move.game_time = datetime.now() - self._tutorial_record.start_time
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
        move.save()
        self._last_move = move

    def map(self):
        return self._map_provider.map()

    def cards(self):
        self._map_provider.cards()
    
    def done(self):
        return self._done

    def has_instructions_todo(self):
        for objective in self._objectives:
            if not objective.completed:
                return True
        return False
    
    # Unimplemented. Exists to satisfy state machine interface.
    def start(self):
        ...

    def update(self):
        self._iter += 1
        self._iter %= 2 ** 32
        # Check to see if the game is out of time.
        if self._turn_state.turns_left == -1:
            logging.info(
                f"Game {self._room_id} is out of turns. Game over!")
            game_over_message = GameOverMessage(
                self._turn_state.game_start,
                self._turn_state.sets_collected,
                self._turn_state.score,
                self._turn_state.turn_number)
            self.record_turn_state(game_over_message)
            self.end_game()
            return

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

                if not self.valid_action(actor_id, proposed_action):
                    actor.drop()
                    self.desync(actor_id)
                    self._record_log.error(f"Resyncing {actor_id} after invalid action.")
                    continue

                if ((not actor.is_realtime()) or actor.peek_action_done()):
                    self.record_move(actor, proposed_action)
                    actor.step()
                    self.record_action(proposed_action)
                    color = Color(0, 0, 1, 1) if not self._current_set_invalid else Color(1, 0, 0, 1)
                    self.check_for_stepped_on_cards(actor_id, proposed_action, color)
                    if self._tutorial_step_index > 0:
                        current_step = self._tutorial_steps[self._tutorial_step_index - 1]
                        if actor.location() in self._step_indicators:
                            logger.info("STEPPED ON INDICATOR!!")
                            self._step_indicators.remove(actor.location())
        
        if self._turn_state.turn != self._player_role:
            # If it's not the player's turn, then the dummy character is moving. If there's no actions left,
            # then return control back to the player.
            current_step = self._tutorial_steps[self._tutorial_step_index - 1]
            if (current_step.tooltip.type == TooltipType.FOLLOWER_TURN) and not self._dummy_character.has_actions():
                logger.info(f"Dummy character has no actions. Advancing to next step.")
                if self._tutorial_step_index > 0:
                    current_step = self._tutorial_steps[self._tutorial_step_index - 1]
                    if current_step.tooltip.type == TooltipType.FOLLOWER_TURN:
                        self.send_next_tutorial_step()

        if len(self._turn_complete_queue) > 0:
            logger.info(f"Turn complete queue has {len(self._turn_complete_queue)} items.")
            reason = self._turn_complete_queue.pop()
            if self._tutorial_step_index != 0:
                current_step = self._tutorial_steps[self._tutorial_step_index - 1]
                # In the tutorial, only allow the player to switch roles if the current step is a role switch.
                if current_step.tooltip.type not in [TooltipType.UNTIL_TURN_ENDED, TooltipType.FOLLOWER_TURN]:
                    logger.info(f"Not sending next tutorial step. current step: {current_step.tooltip}")
                    return
                self.update_turn(force_role_switch=True, end_reason=reason)
                logger.info(f"Sending next tutorial step.")
                self.send_next_tutorial_step()

        # Check to see if the indicator has been reached.
        if self._tutorial_step_index > 0:
            current_step = self._tutorial_steps[self._tutorial_step_index - 1]
            # Check to see if instructions have been followed.
            if (len(current_step.indicators) > 0) and len(self._step_indicators) == 0:
                if current_step.tooltip.type == TooltipType.UNTIL_INDICATOR_REACHED:
                    logger.info("INDICATOR REACHED")
                    self.send_next_tutorial_step()
            # Check to see if instructions have been followed.
            if current_step.tooltip.type == TooltipType.UNTIL_OBJECTIVES_COMPLETED:
                objectives_completed = True
                for objective in self._objectives:
                    if not (objective.completed or objective.cancelled):
                        objectives_completed = False
                        break
                next_step_ready = objectives_completed
                if len(current_step.indicators) > 0:
                    next_step_ready &= (len(self._step_indicators) == 0)
                if next_step_ready:
                    self.send_next_tutorial_step()

        selected_cards = list(self._map_provider.selected_cards())
        cards_changed = False
        if self._map_provider.selected_cards_collide() and not self._current_set_invalid:
            self._current_set_invalid = True
            self._record_log.info("Invalid set detected.")
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
            self._record_log.info("Unique set collected. Awarding points.")
            self._current_set_invalid = False
            added_turns = 0
            cards_changed = True
            if self._turn_state.sets_collected == 0:
                added_turns = 5
            elif self._turn_state.sets_collected in [1, 2]:
                added_turns = 4
            elif self._turn_state.sets_collected in [3, 4]:
                added_turns = 3
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
            set_record = cards_db.CardSets()
            set_record.game = self._tutorial_record
            set_record.move = self._last_move
            set_record.score = new_turn_state.score
            set_record.save()
            for card in selected_cards: 
                card_record = self.get_or_create_card_record(card)
                card_record.set = set_record
                card_record.save()
            self._tutorial_record.score = new_turn_state.score
            self._tutorial_record.save()
            # Clear card state and remove the cards in the winning set.
            logging.info("Clearing selected cards")
            for card in selected_cards:
                self._map_provider.set_selected(card.id, False)
                actions = SetCompletionActions(card.id)
                for action in actions:
                    self.record_action(action)
                self._map_provider.remove_card(card.id)
            # If the tutorial was waiting for a set, advance the tutorial.
            if self._tutorial_step_index > 0:
                current_step = self._tutorial_steps[self._tutorial_step_index - 1]
                if current_step.tooltip.type == TooltipType.UNTIL_SET_COLLECTED:
                    self.send_next_tutorial_step()

        if cards_changed:
            # We've changed cards, so we need to mark the map as stale for all players.
            self._prop_update = self._map_provider.prop_update()
            for actor_id in self._actors:
                self._prop_stale[actor_id] = True

    def update_turn(self, force_role_switch=False, end_reason=""):
        opposite_role = Role.LEADER if self._turn_state.turn == Role.FOLLOWER else Role.FOLLOWER
        role_switch = force_role_switch
        next_role = opposite_role if role_switch else self._turn_state.turn
        # Force the leader to act if there's no uncompleted instructions.
        turn_skipped = False
        if next_role == Role.FOLLOWER and not self.has_instructions_todo():
            next_role = Role.LEADER
            turn_skipped = True
        turns_left = self._turn_state.turns_left
        turn_end = self._turn_state.turn_end
        turn_number = self._turn_state.turn_number
        if role_switch:
            end_of_turn = (next_role == Role.LEADER)
            turn_end = datetime.now() + self.turn_duration(next_role)
            if end_of_turn:
                turns_left -= 1
                turn_number += 1

                # Record the turn end to DB.
                self._tutorial_record.number_turns = self._turn_state.turn_number + 1
                self._tutorial_record.save()

        turn_update = TurnUpdate(
            next_role,
            10,
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
        record, created = cards_db.Card.get_or_create(game=self._tutorial_record, count=card.count,color=str(card.color),shape=str(card.shape),
                                                location=card.location, defaults={"turn_created": self._turn_state.turn_number})
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
            selection_record = cards_db.CardSelections()
            selection_record.game = self._tutorial_record
            selection_record.move = self._last_move
            selection_record.type = "select" if selected else "unselect"
            card_record = self.get_or_create_card_record(stepped_on_card)
            selection_record.card = card_record
            selection_record.save()
    
    def drain_messages(self, id, messages):
        for message in messages:
            self._handle_packet(id, message)

    def _handle_packet(self, id, message):
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
        elif message.type == message_to_server.MessageType.STATE_SYNC_REQUEST:
            logger.info(
                f'Sync request recvd. Room: {self._room_id}, Player: {id}')
            self.desync(id)
        elif message.type == message_to_server.MessageType.TUTORIAL_REQUEST:
            logger.info(f'Tutorial request. Room: {self._room_id}, Player: {id}')
            self.handle_tutorial_request(id, message.tutorial_request)
        elif message.type == message_to_server.MessageType.TURN_COMPLETE:
            logger.info(f'Turn Complete received. Room: {self._room_id}')
            self.handle_turn_complete(id, message.turn_complete)
        elif message.type == message_to_server.MessageType.CANCEL_PENDING_OBJECTIVES:
            logger.info(
                f'Cancel pending objectives recvd. Room: {self._room_id}, Player: {id}')
            self.handle_cancel_pending_objectives(id)
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
        self._recvd_log.info(objective)
        self._objectives.append(objective)
        for actor_id in self._actors:
            self._objectives_stale[actor_id] = True
        self.record_objective(objective)
        # Check to see if the current step can be dismissed by a sent message.
        if self._tutorial_step_index > 0:
            current_step = self._tutorial_steps[self._tutorial_step_index - 1]
            if current_step.tooltip.type == TooltipType.UNTIL_MESSAGE_SENT:
                self.send_next_tutorial_step()

    def handle_turn_complete(self, id, turn_complete):
        if self._actors[id].role() != self._turn_state.turn:
            logger.warn(
                f"Warning, turn complete received from ID: {str(id)} when it isn't their turn!")
            return
        if self._actors[id].role() == Role.LEADER:
            if not self.has_instructions_todo():
                logger.warn(f"Warning, turn complete received from leader ID: {str(id)} when there are no pending instructions!")
                return
        self._recvd_log.info(f"player_id: {id} turn_complete received.")
        if len(self._turn_complete_queue) >= 1:
            logger.warn(
                f"Warning, turn complete queued from ID: {str(id)}, but one was already received! queue size: {len(self._turn_complete_queue)}")
            return
        self._turn_complete_queue.append("UserPrompted")

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
        for actor_id in self._actors:
            self._objectives_stale[actor_id] = True
        instruction = game_db.Instruction.select().where(
            game_db.Instruction.uuid==objective_complete.uuid).get()
        instruction.turn_completed = self._turn_state.turn_number
        instruction.save()
    
    def handle_tutorial_request(self, id, tutorial):
        if tutorial.type == TutorialRequestType.REQUEST_NEXT_STEP:
            if self._tutorial_step_index > 0:
                current_step = self._tutorial_steps[self._tutorial_step_index - 1]
                if (len(current_step.indicators) > 0) and len(self._step_indicators) > 0:
                    logger.warn(f"Received request for next step, but the player hasn't visited the indicator. ID: {id}, Player location: {self._actors[id].location()}")
                    return
                if (current_step.tooltip.type == TooltipType.UNTIL_MESSAGE_SENT):
                    logger.warn(f"Received request for next step, but the player hasn't sent a message yet. ID: {id}")
                    return
                if (current_step.tooltip.type == TooltipType.UNTIL_OBJECTIVES_COMPLETED):
                    for objective in self._objectives:
                        if not (objective.completed or objective.cancelled):
                            logger.warn(f"Received request for next step, but the player hasn't completed the objective. ID: {id}, Objective: {objective}")
                            return
                if (current_step.tooltip.type == TooltipType.FOLLOWER_TURN):
                    logger.warn(f"Received request for next step, but still waiting on dummy character to move. ID: {id}")
                    return
            self.send_next_tutorial_step()
        else:
            logger.warn(f"Received invalid tutorial request type {tutorial.type}")

    def handle_cancel_pending_objectives(self, id):
        if self._actors[id].role() != Role.LEADER:
            logger.warn(
                f'Warning, objective cancellation from non-leader ID: {str(id)}')
            return
        if self._actors[id].role() == self._turn_state.turn:
            logger.warn(
                f'Warning, objective cancellation from leader ID: {str(id)} when it is their turn!')
            return
        # Cancel all objectives.
        for objective in self._objectives:
            if not objective.completed:
                objective.cancelled = True
        self._active_objective = None
        for actor_id in self._actors:
            self._objectives_stale[actor_id] = True
        self._turn_complete_queue.append("LeaderInterrupt")

    
    def send_next_tutorial_step(self):
        if self._tutorial_step_index >= len(self._tutorial_steps):
            self._tutorial_record.completed = True
            self._tutorial_record.end_time = datetime.now()
            self._tutorial_record.save()
            self._tutorial_responses.put(TutorialCompletedResponse(self._tutorial_name))
            self.end_game()
            return
        self.record_turn_state(self._turn_state)
        next_step = self._tutorial_steps[self._tutorial_step_index]
        logger.info(f"Preparing step {self._tutorial_step_index + 1} of {len(self._tutorial_steps)}.")
        self._tutorial_responses.put(TutorialResponseFromStep(self._tutorial_name, next_step))
        instruction = next_step.instruction
        if instruction is not None:
            objective = ObjectiveMessage()
            objective.text = instruction.text
            objective.completed = False
            objective.uuid = uuid.uuid4().hex
            self._objectives.append(objective)
            self.record_objective(objective)
            for actor_id in self._actors:
                self._objectives_stale[actor_id] = True
        if next_step.indicators is not None and (next_step.tooltip.type == TooltipType.UNTIL_INDICATOR_REACHED):
            self._step_indicators = set([i.location for i in next_step.indicators])
        if next_step.other_player_turn is not None:
            logger.info(f"Sending {len(next_step.other_player_turn)} dummy actions...")
            for action in next_step.other_player_turn:
                logger.info("Sending dummy action: " + str(action))
                if action == FollowerActions.FORWARDS:
                    self._dummy_character.WalkForwards()
                elif action == FollowerActions.BACKWARDS:
                    self._dummy_character.WalkBackwards()
                elif action == FollowerActions.TURN_LEFT:
                    self._dummy_character.TurnLeft()
                elif action == FollowerActions.TURN_RIGHT:
                    self._dummy_character.TurnRight()
                elif action == FollowerActions.INSTRUCTION_DONE:
                    objective_hash = None
                    for objective in self._objectives:
                        if not objective.completed and not objective.cancelled:
                            objective_hash = objective.uuid
                            break
                    objective_complete = ObjectiveCompleteMessage(objective_hash)
                    self.handle_objective_complete(self._dummy_character.actor_id(), objective_complete)
                elif action == FollowerActions.END_TURN:
                    if self._turn_state.turn == self._dummy_character.role():
                        self._turn_complete_queue.append("Tutorial dummy cedes control.")
                else:
                    logger.warn(f"Warning, unknown follower action: {action}")
        self._tutorial_step_index += 1

    def create_actor(self, role, realtime=False):
        spawn_point = self._spawn_points.pop() if self._spawn_points else HecsCoord(0, 0, 0)
        print(spawn_point)
        asset_id = AssetId.PLAYER if role == Role.LEADER else AssetId.FOLLOWER_BOT
        actor = Actor(self._id_assigner.alloc(), asset_id, role, spawn_point, realtime)
        self._actors[actor.actor_id()] = actor
        self._action_history[actor.actor_id()] = []
        self._synced[actor.actor_id()] = False
        # Mark clients as desynced.
        self.desync_all()

        # Send a TurnState with unlimited moves, time left.
        turn_update = TurnUpdate(self._player_role,
                                    10,
                                    10,
                                    datetime.now() + timedelta(minutes=1),
                                    self._turn_state.game_start,
                                    self._turn_state.sets_collected,
                                    self._turn_state.score, 0)
        self.record_turn_state(turn_update)

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
                logger.info("Pending actions")
                return True
            if self._objectives_stale[actor_id]:
                logger.info("Pending objectives")
                return True
            if not self._turn_history[actor_id].empty():
                logger.info("Pending turn history")
                return True
            if not self._tutorial_responses.empty():
                return True
        return False

    def fill_messages(self, player_id, out_messages: List[message_from_server.MessageFromServer]):
        """ Serializes all messages to one player into a linear history. 
        
            If any messages have been generated this iteration, caps those
            messages with a StateMachineTick. This lets us separate logic
            iterations on the receive side.
        """
        # Don't send messages to the dummy player.
        if player_id == self._dummy_character.actor_id():
            return False
        message = self._next_message(player_id)
        messages_added = 0
        while message != None:
            out_messages.append(message)
            messages_added += 1
            message = self._next_message(player_id)
            logger.info(f"Filling message: {message} for player {player_id}")

        if messages_added == 0:
            return False

        # We sent messages this iteration. Send a tick.
        tick_message = StateMachineTick(iter=self._iter)
        message = message_from_server.StateMachineTickFromServer(tick_message)
        out_messages.append(message)
        return True


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
                f'Room {self._room_id} prop update {prop_update} for player_id {player_id}')
            return message_from_server.PropUpdateFromServer(prop_update)

        if not self.is_synced(player_id):
            state_sync = self.sync_message_for_transmission(player_id)
            logger.debug(
                f'Room {self._room_id} state sync: {state_sync} for player_id {player_id}')
            msg = message_from_server.StateSyncFromServer(state_sync)
            return msg

        objectives = self._next_objectives(player_id)
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

        tutorial_response = self._next_tutorial_response(player_id)
        if tutorial_response is not None:
            logger.info(
                f'Room {self._room_id} tr {tutorial_response} for player_id {player_id}')
            msg = message_from_server.TutorialResponseFromServer(tutorial_response)
            return msg

        # Nothing to send.
        return None

    def _next_actions(self, actor_id):
        actor = self._actors[actor_id]
        if not actor_id in self._action_history:
            return []
        action_history = self._action_history[actor_id]

        if actor.role() == Role.FOLLOWER:
            action_history = [CensorActionForFollower(action, actor) for action in action_history]

        # Log actions sent to client.
        for action in action_history:
            self._sent_log.info(f"to: {actor_id} action: {action}")
        self._action_history[actor_id] = []
        return action_history

    def _next_objectives(self, actor_id):
        if not actor_id in self._objectives_stale:
            self._objectives_stale[actor_id] = True
        
        if not self._objectives_stale[actor_id]:
            return []
        
        # Send the latest objective list and mark as fresh for this player.
        self._objectives_stale[actor_id] = False
        self._sent_log.info(f"to: {actor_id} objectives: {self._objectives}")
        return self._objectives
    
    def _next_map_update(self, actor_id):
        if not actor_id in self._map_stale:
            self._map_stale[actor_id] = True
        
        if not self._map_stale[actor_id]:
            return None

        map_update = self._map_update

        if self._actors[actor_id].role() == Role.FOLLOWER:
            map_update = map_utils.CensorMapForFollower(map_update, self._actors[actor_id])

        self._map_update_count += 1

        # Record the map update to the database.
        map_record = map_db.MapUpdate()
        map_record.world_seed = ""
        map_record.map_data = map_update
        map_record.game = self._tutorial_record
        map_record.map_update_number = self._map_update_count
        map_record.save()
        
        # Send the latest map and mark as fresh for this player.
        self._map_stale[actor_id] = False
        self._sent_log.info(f"to: {actor_id} map: {map_update}")
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
        prop_record = prop_db.PropUpdate()
        prop_record.prop_data = prop_update
        prop_record.game = self._tutorial_record
        prop_record.save()
        
        self._prop_stale[actor_id] = False
        return prop_update

    def _next_tutorial_response(self, actor_id):
        if self._tutorial_responses.empty():
            return None
        return self._tutorial_responses.get()


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
                return False
        if (action.action_type == ActionType.ROTATE):
            if (action.rotation > 60.01):
                return False
        return True

    def on_game_over(self):
        # Make sure to mark the game's end time.
        self._tutorial_record.end_time = datetime.now()
        self._tutorial_record.save()