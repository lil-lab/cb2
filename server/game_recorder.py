import logging
import queue
import random
from datetime import datetime
from queue import Queue
from typing import List

import orjson

import server.messages.live_feedback as live_feedback
import server.schemas as schemas
from server.hex import HecsCoord
from server.messages.action import Action
from server.messages.rooms import Role
from server.schemas.game import Event, EventOrigin, EventType

logger = logging.getLogger(__name__)


def EventFromMapUpdate(game, tick: int, map_update):
    return Event(
        game=game,
        type=EventType.MAP_UPDATE,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=map_update.to_json(),
    )


def EventFromStateSync(game, tick: int, state_sync):
    return Event(
        game=game,
        type=EventType.STATE_SYNC,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=state_sync.to_json(),
    )


def EventFromPropUpdate(game, tick: int, prop_update):
    return Event(
        game=game,
        type=EventType.PROP_UPDATE,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=prop_update.to_json(),
    )


def EventFromTurnState(game, tick: int, origin: EventOrigin, turn_state):
    return Event(
        game=game,
        type=EventType.TURN_STATE,
        tick=tick,
        origin=origin,
        data=turn_state.to_json(),
    )


def EventFromCardSpawn(game, tick: int, origin: EventOrigin, card):
    return Event(
        game=game,
        type=EventType.CARD_SPAWN,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=card.to_json(),
        location=card.location,
        orientation=card.orientation,
    )


def EventFromCardSelect(game, tick: int, origin: EventOrigin, card, last_move):
    short_code = "select" if card.selected else "unselect"
    return Event(
        game=game,
        type=EventType.CARD_SELECT,
        tick=tick,
        origin=origin,
        parent_event=last_move,
        data=card.to_json(),
        short_code=short_code,
        location=card.location,
        orientation=card.orientation,
    )


def EventFromCardSet(
    game, tick: int, origin: EventOrigin, cardset: List, score, last_move
):
    data = {
        "cards": [card.to_dict() for card in cardset],
        "score": score,
    }
    return Event(
        game=game,
        type=EventType.CARD_SET,
        tick=tick,
        origin=origin,
        parent_event=last_move,
        data=orjson.dumps(data),
    )


def EventFromInstructionSent(game, tick: int, instruction):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_SENT,
        tick=tick,
        origin=EventOrigin.LEADER,
        data=instruction.to_json(),
    )


def EventFromInstructionActivated(game, tick, instruction_event):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_ACTIVATED,
        tick=tick,
        origin=EventOrigin.SERVER,
        parent_event=instruction_event,
    )


def EventFromInstructionDone(game, tick, instruction_event):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_DONE,
        tick=tick,
        origin=EventOrigin.FOLLOWER,
        parent_event=instruction_event,
    )


def EventFromInstructionCancelled(game, tick, instruction_event):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_CANCELLED,
        tick=tick,
        origin=EventOrigin.FOLLOWER,
        parent_event=instruction_event,
    )


def EventFromMove(
    game,
    tick: int,
    origin: EventOrigin,
    action,
    location_before,
    orientation_before,
    instruction_event,
):
    return Event(
        game=game,
        type=EventType.MOVE,
        tick=tick,
        origin=origin,
        parent_event=instruction_event,
        data=action.to_json(),
        location=location_before,
        orientation=orientation_before,
    )


def EventFromLiveFeedback(
    game, tick: int, feedback: live_feedback.LiveFeedback, last_move
):
    return Event(
        game=game,
        type=EventType.LIVE_FEEDBACK,
        tick=tick,
        origin=EventOrigin.SERVER,
        parent_event=last_move,
        data=feedback.to_json(),
    )


class GameRecorder(object):
    """Helper class to record everything that happens in a game.

    Logs all messages and also populates the database.
    """

    def __init__(self, game_record, disabled=False):
        """Parameter disabled is used to disable logging. Useful for testing and certain other situations."""
        self._disabled = disabled
        if self._disabled:
            return
        self._last_move = None
        self._active_instruction = None
        self._last_turn_state = None
        self._instruction_number = 1
        self._instruction_queue = Queue()

        # Create an entry in the Game database table.
        self._game_record = game_record
        self._game_record.world_seed = repr(random.getstate())
        self._game_record.score = 0
        self._game_record.valid = True
        self._game_record.who_is_agent = ""
        self._game_record.save()

    def record(self):
        if self._disabled:
            return None
        return self._game_record

    def initial_state(self, map_update, prop_update, turn_state, actors):
        if self._disabled:
            return
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
            logger.warn(
                f"Unable to log initial state for game {self._game_record.id}. Leader or follower None."
            )
            return
        initial_state = schemas.game.InitialState(
            game=self._game_record,
            leader_id=leader.actor_id(),
            follower_id=follower.actor_id(),
            leader_position=leader.location(),
            leader_rotation_degrees=leader.heading_degrees(),
            follower_position=follower.location(),
            follower_rotation_degrees=follower.heading_degrees(),
        )
        initial_state.save()

    def record_map_update(self, tick, map_update):
        if self._disabled:
            return
        event = EventFromMapUpdate(self._game_record, tick, map_update)
        event.save()

    def record_prop_update(self, prop_update):
        if self._disabled:
            return
        # Record the prop update to the database.
        EventFromPropUpdate(self._game_record, tick, prop_update)
        prop_record = schemas.prop.PropUpdate()
        prop_record.prop_data = prop_update
        prop_record.game = self._game_record
        prop_record.save()

    def record_card_selection(self, card):
        if self._disabled:
            return
        selection_record = schemas.cards.CardSelections()
        selection_record.game = self._game_record
        selection_record.move = self._last_move
        selection_record.type = "select" if card.selected else "unselect"
        card_record = self._get_or_create_card_record(card)
        selection_record.card = card_record
        selection_record.save()

    def record_card_set(self):
        if self._disabled:
            return
        set_record = schemas.cards.CardSets()
        set_record.game = self._game_record
        set_record.move = self._last_move
        set_record.score = self._last_turn_state.score + 1
        set_record.save()

    def record_instruction(self, objective):
        if self._disabled:
            return
        instruction = schemas.game.Instruction()
        instruction.game = self._game_record
        instruction.time = datetime.utcnow()
        instruction.worker = self._game_record.leader
        instruction.uuid = objective.uuid
        instruction.text = objective.text
        instruction.instruction_number = self._instruction_number
        self._instruction_number += 1
        instruction.turn_issued = self._last_turn_state.turn_number
        instruction.save()

        if self._active_instruction is None:
            self._set_activated_instruction(objective)
        else:
            try:
                self._instruction_queue.put_nowait(objective)
            except queue.Full:
                return

    def _set_activated_instruction(self, next_active_instruction):
        self._active_instruction = next_active_instruction
        activated_instruction_entry = (
            schemas.game.Instruction.select()
            .where(schemas.game.Instruction.uuid == self._active_instruction.uuid)
            .get()
        )
        activated_instruction_entry.turn_activated = self._last_turn_state.turn_number
        activated_instruction_entry.save()

    def record_instruction_complete(self, objective_complete, actor):
        if self._disabled:
            return
        instruction = (
            schemas.game.Instruction.select()
            .where(schemas.game.Instruction.uuid == objective_complete.uuid)
            .get()
        )
        instruction.turn_completed = self._last_turn_state.turn_number
        instruction.save()
        # Log an entry in the move table for this instruction.
        self.record_move(actor=actor, proposed_action=None, instruction_done=True)
        try:
            next_active_instruction = self._instruction_queue.get_nowait()
            self._set_activated_instruction(next_active_instruction)
        except queue.Empty:
            self._active_instruction = None

    def record_move(
        self, actor, proposed_action: Action = None, instruction_done=False
    ):
        if self._disabled:
            return
        assert (
            instruction_done or proposed_action is not None
        ), "Must provide an action or set instruction_done to True"
        move = schemas.game.Move()
        move.game = self._game_record
        if actor.role() == Role.FOLLOWER:
            if self._active_instruction is not None:
                last_obj_record = (
                    schemas.game.Instruction.select()
                    .where(
                        schemas.game.Instruction.uuid == self._active_instruction.uuid
                    )
                    .get()
                )
                move.instruction = last_obj_record
        move.character_role = actor.role()
        if actor.role == Role.LEADER:
            move.worker = self._game_record.leader
        if actor.role == Role.FOLLOWER:
            move.worker = self._game_record.follower
        if proposed_action is not None:
            move.action = proposed_action
        move.position_before = actor.location()
        move.orientation_before = actor.heading_degrees()
        if self._last_turn_state is not None:
            move.turn_number = self._last_turn_state.turn_number
        move.game_time = datetime.utcnow() - self._game_record.start_time
        move.server_time = datetime.utcnow()
        move_code = ""
        if instruction_done:
            # Use a default, invalid action object for json.
            move.action = Action()
            move.action_code = "DONE"
            self._last_move = move
            move.save()
            return
        # instruction_done == False. We have a proposed action. Calculate move code...
        forward_location = actor.location().neighbor_at_heading(actor.heading_degrees())
        backward_location = actor.location().neighbor_at_heading(
            actor.heading_degrees() + 180
        )
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
        self._last_move = move
        move.save()

    def record_live_feedback(self, feedback, follower):
        if self._disabled:
            return
        # TODO(sharf): Once we add a move column to live feedback. we can record
        # the move that the live feedback is for.
        live_feedback_record = schemas.game.LiveFeedback()
        live_feedback_record.game = self._game_record
        live_feedback_record.feedback_type = (
            "POSITIVE"
            if feedback.signal == live_feedback.FeedbackType.POSITIVE
            else "NEGATIVE"
        )

        # Find the instruction that the feedback is for.
        if self._active_instruction is not None:
            last_obj_record = (
                schemas.game.Instruction.select()
                .where(schemas.game.Instruction.uuid == self._active_instruction.uuid)
                .get()
            )
            live_feedback_record.instruction = last_obj_record
        live_feedback_record.turn_number = self._last_turn_state.turn_number
        if follower is not None:
            live_feedback_record.follower_position = follower.location()
            live_feedback_record.follower_orientation = follower.heading_degrees()
        live_feedback_record.game_time = (
            datetime.utcnow() - self._game_record.start_time
        )
        live_feedback_record.server_time = datetime.utcnow()
        live_feedback_record.save()

    def mark_instruction_cancelled(self, objective):
        if self._disabled:
            return
        instruction_query = schemas.game.Instruction.select().where(
            schemas.game.Instruction.uuid == objective.uuid
        )
        if instruction_query.count() == 0:
            logger.warn(f"Could not find instruction record for {objective.uuid}")
            return
        instruction = instruction_query.get()
        logger.info(f"Canceling instruction {instruction.text}")
        instruction.turn_cancelled = self._last_turn_state.turn_number
        instruction.save()

    def record_instruction_cancellation(self):
        if self._disabled:
            return
        if self._active_instruction != None:
            self.mark_instruction_cancelled(self._active_instruction)
        self._active_instruction = None
        try:
            while True:
                objective = self._instruction_queue.get_nowait()
                if not objective.completed and not objective.cancelled:
                    self.mark_instruction_cancelled(objective)
        except queue.Empty:
            return

    def record_end_of_turn(self, force_role_switch, end_reason, turn_skipped):
        if self._disabled:
            return
        turn = schemas.game.Turn()
        turn.game = self._game_record
        # Due to a change in how turns are counted, each turn now
        # includes movements for both roles. This field is now deprecated.
        turn.role = ""
        turn.turn_number = (
            self._last_turn_state.turn_number
        )  # Recording the turn that just ended.
        end_method = end_reason if force_role_switch else "RanOutOfTime"
        turn.end_method = end_method
        notes = []
        if turn_skipped:
            notes.append("SkippedTurnNoInstructionsTodo")
        if self._last_turn_state.moves_remaining <= 0:
            notes.append("UsedAllMoves")
        if (
            self._last_turn_state.turn == Role.FOLLOWER
            and self._instruction_queue.empty()
        ):
            notes.append("FinishedAllCommands")
        turn.notes = ",".join(notes)
        turn.save()

    def record_turn_state(self, turn_state):
        if self._disabled:
            return
        self._last_turn_state = turn_state
        self._game_record.score = turn_state.score
        self._game_record.number_turns = turn_state.turn_number
        self._game_record.save()

    def record_game_over(self):
        if self._disabled:
            return
        self._game_record.completed = True
        self._game_record.end_time = datetime.utcnow()
        self._game_record.score = self._last_turn_state.score
        self._game_record.save()

    def kvals(self):
        if self._game_record.kvals is None:
            return {}
        return orjson.loads(self._game_record.kvals)

    def set_kvals(self, kvals):
        self._game_record.kvals = orjson.dumps(kvals)
        self._game_record.save()

    def _get_or_create_card_record(self, card):
        if self._disabled:
            return
        record, created = schemas.cards.Card.get_or_create(
            game=self._game_record,
            count=card.count,
            color=str(card.color),
            shape=str(card.shape),
            location=card.location,
            defaults={"turn_created": self._last_turn_state.turn_number},
        )
        return record
