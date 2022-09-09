import logging
import queue
import random

import server.schemas as schemas
import server.messages.live_feedback as live_feedback

from datetime import datetime
from queue import Queue

from server.messages.action import Action
from server.messages.rooms import Role
from server.hex import HecsCoord

logger = logging.getLogger(__name__)

class GameRecorder(object):
    """ Helper class to record everything that happens in a game.

        Logs all messages and also populates the database.
    """
    def __init__(self, game_record):
        self._last_move = None
        self._active_objective = None
        self._last_turn_state = None
        self._objective_number = 1
        self._active_objective = None
        self._objective_queue = Queue()
        self._map_update_count = 1

        # Create an entry in the Game database table.
        self._game_record = game_record
        self._game_record.world_seed = repr(random.getstate())
        self._game_record.score = 0
        self._game_record.valid = True
        self._game_record.who_is_agent = ""
        self._game_record.save()
    
    def record(self):
        return self._game_record
    
    def initial_state(self, map_update, prop_update, turn_state, actors):
        self._game_record.number_cards = len(prop_update.props)
        self._game_record.save()
        self._last_turn_state = turn_state
        leader = None
        follower = None
        for id in actors:
            actor = actors[id]
            if actor.role() == Role.LEADER:
                leader = actor
            elif actor.role() == Role.FOLLOWER:
                follower = actor
        if leader is None or follower is None:
            logger.warn(f"Unable to log initial state for game {self._game_record.id}. Leader or follower None.")
            return
        initial_state = schemas.game.InitialState(
            game = self._game_record,
            leader_id = leader.actor_id(),
            follower_id = follower.actor_id(),
            leader_position = leader.location(),
            leader_rotation_degrees=leader.heading_degrees(),
            follower_position = follower.location(),
            follower_rotation_degrees=follower.heading_degrees()
        )
        initial_state.save()

    def record_map_update(self, map_update):
        # Record the map update to the database.
        map_record = schemas.map.MapUpdate()
        map_record.world_seed = self._game_record.world_seed
        map_record.map_data = map_update
        map_record.game = self._game_record
        map_record.map_update_number = self._map_update_count
        self._map_update_count += 1
        map_record.save()
    
    def record_prop_update(self, prop_update):
        # Record the prop update to the database.
        prop_record = schemas.prop.PropUpdate()
        prop_record.prop_data = prop_update
        prop_record.game = self._game_record
        prop_record.save()
    
    def record_card_selection(self, card):
        selection_record = schemas.cards.CardSelections()
        selection_record.game = self._game_record
        selection_record.move = self._last_move
        selection_record.type = "select" if card.selected else "unselect"
        card_record = self._get_or_create_card_record(card)
        selection_record.card = card_record
        selection_record.save()
    
    def record_card_set(self):
            set_record = schemas.cards.CardSets()
            set_record.game = self._game_record
            set_record.move = self._last_move
            set_record.score = self._last_turn_state.score + 1
            set_record.save()

    def record_objective(self, objective):
        instruction = schemas.game.Instruction()
        instruction.game = self._game_record
        instruction.time = datetime.utcnow()
        instruction.worker = self._game_record.leader
        instruction.uuid = objective.uuid
        instruction.text = objective.text
        instruction.instruction_number = self._objective_number
        self._objective_number +=1
        instruction.turn_issued = self._last_turn_state.turn_number
        instruction.save()

        if self._active_objective is None:
            self._active_objective = objective
        else:
            try:
                self._objective_queue.put_nowait(objective)
            except queue.Full:
                return
    
    def record_objective_complete(self, objective_complete):
        instruction = schemas.game.Instruction.select().where(
            schemas.game.Instruction.uuid==objective_complete.uuid).get()
        instruction.turn_completed = self._last_turn_state.turn_number
        instruction.save()
        try:
            next_active_objective = self._objective_queue.get_nowait()
            self._active_objective = next_active_objective
        except queue.Empty:
            self._active_objective = None
    
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
            move.worker = self._game_record.leader
        if actor.role == Role.FOLLOWER:
            move.worker = self._game_record.follower
        move.action = proposed_action
        move.position_before = actor.location()
        move.orientation_before = actor.heading_degrees()
        if self._last_turn_state != None:
            move.turn_number = self._last_turn_state.turn_number
        move.game_time = datetime.utcnow() - self._game_record.start_time
        move.server_time = datetime.utcnow()
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
    
    def record_live_feedback(self, feedback, follower):
        # TODO(sharf): Once we add a move column to live feedback. we can record
        # the move that the live feedback is for.
        live_feedback_record = schemas.game.LiveFeedback()
        live_feedback_record.game = self._game_record
        live_feedback_record.feedback_type = "POSITIVE" if feedback.signal == live_feedback.FeedbackType.POSITIVE else "NEGATIVE"
        
        # Update the follower's state.
        if self._active_objective is not None:
            last_obj_record = schemas.game.Instruction.select().where(
                schemas.game.Instruction.uuid == self._active_objective.uuid).get()
            live_feedback_record.instruction = last_obj_record
        live_feedback_record.turn_number = self._last_turn_state.turn_number
        if follower is not None:
            live_feedback_record.follower_position = follower.location()
            live_feedback_record.follower_orientation = follower.heading_degrees()
        live_feedback_record.game_time = datetime.utcnow() - self._game_record.start_time
        live_feedback_record.server_time = datetime.utcnow()
        live_feedback_record.save()
    
    def record_instruction_cancellation(self):
        self._active_objective = None
        try:
            while True:
                objective = self._objective_queue.get_nowait()
                if not objective.completed:
                    instruction = schemas.game.Instruction.select().where(
                        schemas.game.Instruction.uuid==objective.uuid).get()
                    instruction.turn_cancelled = self._last_turn_state.turn_number
                    instruction.save()
        except queue.Empty:
            return
    
    def record_end_of_turn(self, force_role_switch, end_reason, turn_skipped):
        turn = schemas.game.Turn()
        turn.game = self._game_record
        # Due to a change in how turns are counted, each turn now
        # includes movements for both roles. This field is now deprecated.
        turn.role = ""
        turn.turn_number = self._last_turn_state.turn_number  # Recording the turn that just ended.
        end_method = end_reason if force_role_switch else "RanOutOfTime"
        turn.end_method = end_method
        notes = []
        if turn_skipped:
            notes.append("SkippedTurnNoInstructionsTodo")
        if self._last_turn_state.moves_remaining <= 0:
            notes.append("UsedAllMoves")
        if self._last_turn_state.turn == Role.FOLLOWER and self._objective_queue.empty():
            notes.append("FinishedAllCommands")
        turn.notes = ",".join(notes)
        turn.save()
    
    def record_turn_state(self, turn_state):
        self._last_turn_state = turn_state
        self._game_record.score = turn_state.score
        self._game_record.number_turns = turn_state.turn_number
        self._game_record.save()

    def record_game_over(self):
        self._game_record.completed = True
        self._game_record.end_time = datetime.utcnow()
        self._game_record.score = self._last_turn_state.score
        self._game_record.save()

    def _get_or_create_card_record(self, card):
        record, created = schemas.cards.Card.get_or_create(game=self._game_record, count=card.count,color=str(card.color),shape=str(card.shape),
                                                location=card.location, defaults={'turn_created': self._last_turn_state.turn_number})
        return record