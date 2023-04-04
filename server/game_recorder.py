import logging
import random
from datetime import datetime
from queue import Queue
from typing import List

import orjson

import server.messages.live_feedback as live_feedback
import server.schemas as schemas
from server.card import Card
from server.hex import HecsCoord
from server.messages.action import Action
from server.messages.feedback_questions import FeedbackQuestion, FeedbackResponse
from server.messages.rooms import Role
from server.schemas.event import Event, EventOrigin, EventType
from server.schemas.util import InitialState

logger = logging.getLogger(__name__)


def JsonSerialize(x):
    pretty_dumper = lambda x: orjson.dumps(
        x,
        option=orjson.OPT_NAIVE_UTC
        | orjson.OPT_INDENT_2
        | orjson.OPT_PASSTHROUGH_DATETIME,
        default=datetime.isoformat,
    ).decode("utf-8")
    return pretty_dumper(x)


def EventFromMapUpdate(game, tick: int, map_update):
    return Event(
        game=game,
        type=EventType.MAP_UPDATE,
        turn_number=0,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=JsonSerialize(map_update),
    )


def EventFromInitialState(game, tick: int, leader, follower):
    initial_state = InitialState(
        leader_id=leader.actor_id() if leader else -1,
        follower_id=follower.actor_id() if follower else -1,
        leader_position=leader.location() if leader else HecsCoord(a=-1, r=-1, c=-1),
        leader_rotation_degrees=leader.heading_degrees() if leader else -1,
        follower_position=follower.location()
        if follower
        else HecsCoord(a=-1, r=-1, c=-1),
        follower_rotation_degrees=follower.heading_degrees() if follower else -1,
    )
    return Event(
        game=game,
        type=EventType.INITIAL_STATE,
        turn_number=0,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=JsonSerialize(initial_state),
    )


def EventFromPropUpdate(game, tick: int, prop_update):
    return Event(
        game=game,
        type=EventType.PROP_UPDATE,
        turn_number=0,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=JsonSerialize(prop_update),
    )


def EventFromTurnState(game, tick: int, turn_state, short_code):
    return Event(
        game=game,
        type=EventType.TURN_STATE,
        turn_number=turn_state.turn_number,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=JsonSerialize(turn_state),
        short_code=short_code,
        role=turn_state.turn,
    )


def EventFromStartOfTurn(game, tick: int, turn_state, short_code):
    return Event(
        game=game,
        type=EventType.START_OF_TURN,
        turn_number=turn_state.turn_number,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=JsonSerialize(turn_state),
        short_code=short_code,
        role=turn_state.turn,
    )


def EventFromCardSpawn(game, turn: int, tick: int, card: Card):
    card_str = " ".join([str(card.count), str(card.color), str(card.shape)])
    return Event(
        game=game,
        type=EventType.CARD_SPAWN,
        turn_number=turn,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=JsonSerialize(card),
        location=card.location,
        orientation=card.rotation_degrees,
        short_code=card_str,
    )


def EventFromCardSelect(
    game, turn: int, tick: int, origin: EventOrigin, card: Card, last_move
):
    short_code = "select" if card.selected else "unselect"
    role = Role.NONE
    if origin == EventOrigin.LEADER:
        role = Role.LEADER
    elif origin == EventOrigin.FOLLOWER:
        role = Role.FOLLOWER
    return Event(
        game=game,
        type=EventType.CARD_SELECT,
        turn_number=turn,
        tick=tick,
        origin=origin,
        parent_event=last_move,
        data=JsonSerialize(card),
        short_code=short_code,
        location=card.location,
        orientation=card.rotation_degrees,
        role=role,
    )


def EventFromCardSet(
    game,
    turn: int,
    tick: int,
    origin: EventOrigin,
    cardset: List[Card],
    score,
    last_move,
):
    data = {
        "cards": [card.to_dict() for card in cardset],
        "score": score,
    }
    return Event(
        game=game,
        type=EventType.CARD_SET,
        turn_number=turn,
        tick=tick,
        origin=origin,
        parent_event=last_move,
        data=JsonSerialize(data),
        short_code=score,
    )


def EventFromInstructionSent(game, turn: int, tick: int, instruction):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_SENT,
        turn_number=turn,
        tick=tick,
        origin=EventOrigin.LEADER,
        role=Role.LEADER,
        short_code=instruction.uuid,
        data=JsonSerialize(instruction),
    )


def EventFromInstructionActivated(game, turn: int, tick, instruction_event, uuid):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_ACTIVATED,
        turn_number=turn,
        tick=tick,
        origin=EventOrigin.SERVER,
        role=Role.NONE,
        parent_event=instruction_event,
        short_code=uuid,
    )


def EventFromInstructionDone(game, turn: int, tick: int, instruction_event, uuid):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_DONE,
        turn_number=turn,
        tick=tick,
        origin=EventOrigin.FOLLOWER,
        role=Role.FOLLOWER,
        parent_event=instruction_event,
        short_code=uuid,
    )


def EventFromInstructionCancelled(
    game, turn: int, tick: int, instruction_event, instruction_uuid
):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_CANCELLED,
        turn_number=turn,
        tick=tick,
        origin=EventOrigin.LEADER,
        role=Role.LEADER,
        parent_event=instruction_event,
        short_code=instruction_uuid,
    )


def EventFromAction(
    game,
    turn: int,
    tick: int,
    origin: EventOrigin,
    action,
    location_before,
    orientation_before,
    action_code,
    instruction_event=None,
):
    role = Role.NONE
    if origin == EventOrigin.LEADER:
        role = Role.LEADER
    elif origin == EventOrigin.FOLLOWER:
        role = Role.FOLLOWER
    return Event(
        game=game,
        type=EventType.ACTION,
        turn_number=turn,
        tick=tick,
        origin=origin,
        parent_event=instruction_event,
        data=JsonSerialize(action),
        location=location_before,
        orientation=orientation_before,
        short_code=action_code,
        role=role,
    )


def EventFromLiveFeedback(
    game,
    turn: int,
    tick: int,
    feedback: live_feedback.LiveFeedback,
    follower,
    last_move,
):
    short_code = ""
    if feedback.signal == live_feedback.FeedbackType.POSITIVE:
        short_code = "Positive"
    elif feedback.signal == live_feedback.FeedbackType.NEGATIVE:
        short_code = "Negative"
    elif feedback.signal == live_feedback.FeedbackType.NONE:
        short_code = "None"
    else:
        short_code = "Unknown"
    return Event(
        game=game,
        type=EventType.LIVE_FEEDBACK,
        turn_number=turn,
        tick=tick,
        origin=EventOrigin.LEADER,
        role=Role.LEADER,
        parent_event=last_move,
        data=JsonSerialize(feedback),
        short_code=short_code,
        location=follower.location(),
        orientation=follower.heading_degrees(),
    )


def EventFromFeedbackQuestion(game, turn: int, tick: int, question: FeedbackQuestion):
    return Event(
        game=game,
        type=EventType.FEEDBACK_QUESTION,
        turn_number=turn,
        tick=tick,
        origin=EventOrigin.SERVER,
        role=question.to,
        short_code=question.uuid,
        data=JsonSerialize(question),
    )


def EventFromFeedbackResponse(
    game, turn: int, tick: int, question_event, response: FeedbackResponse
):
    return Event(
        game=game,
        type=EventType.FEEDBACK_RESPONSE,
        turn_number=turn,
        tick=tick,
        origin=EventOrigin.SERVER,
        role=question_event.role,
        parent_event=question_event,
        short_code=response.uuid,
        data=JsonSerialize(response),
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
        self._instruction_number = 1
        self._instruction_queue = Queue()
        self._tick = 0
        self._turn_number = 0

        # Create an entry in the Game database table.
        self._game_record = game_record
        self._game_record.world_seed = repr(random.getstate())
        self._game_record.score = 0
        self._game_record.valid = True
        self._game_record.who_is_agent = ""
        self._game_record.save()

        self._last_follower_move = None

    def record(self):
        if self._disabled:
            return None
        return self._game_record

    def record_initial_state(
        self, tick, map_update, prop_update, turn_state, leader, follower
    ):
        if self._disabled:
            return
        self._game_record.number_cards = len(prop_update.props)
        self._game_record.save()

        if leader is None and follower is None:
            logger.warn(
                f"Unable to log initial state for game {self._game_record.id}. Leader or follower None."
            )
            return
        initial_state_event = EventFromInitialState(
            self._game_record, tick, leader, follower
        )
        initial_state_event.save(force_insert=True)
        self.record_map_update(map_update)
        self.record_turn_state(turn_state)
        self.record_prop_update(prop_update)

    def record_tick(self, tick: int):
        self._tick = tick

    def record_map_update(self, map_update):
        if self._disabled:
            return
        event = EventFromMapUpdate(self._game_record, self._tick, map_update)
        event.save(force_insert=True)

    def record_prop_update(self, prop_update):
        if self._disabled:
            return
        # Record the prop update to the database.
        event = EventFromPropUpdate(self._game_record, self._tick, prop_update)
        event.save(force_insert=True)

    def record_card_spawn(self, card: Card):
        if self._disabled:
            return
        event = EventFromCardSpawn(
            self._game_record, self._turn_number, self._tick, card
        )
        event.save(force_insert=True)

    def record_card_selection(self, actor, card: Card):
        if self._disabled:
            return
        origin = EventOrigin.NONE
        if actor is not None:
            if actor.role() == Role.LEADER:
                origin = EventOrigin.LEADER
            elif actor.role() == Role.FOLLOWER:
                origin = EventOrigin.FOLLOWER
        event = EventFromCardSelect(
            self._game_record,
            self._turn_number,
            self._tick,
            origin,
            card,
            self._last_move,
        )
        event.save(force_insert=True)

    def record_card_set(self, actor, cards: List[Card], score):
        if self._disabled:
            return
        origin = EventOrigin.NONE
        if actor is not None:
            if actor.role() == Role.LEADER:
                origin = EventOrigin.LEADER
            elif actor.role() == Role.FOLLOWER:
                origin = EventOrigin.FOLLOWER
        event = EventFromCardSet(
            self._game_record,
            self._turn_number,
            self._tick,
            origin,
            cards,
            score,
            self._last_move,
        )
        event.save(force_insert=True)

    def record_instruction_sent(self, objective):
        if self._disabled:
            return
        event = EventFromInstructionSent(
            self._game_record, self._turn_number, self._tick, objective
        )
        event.save(force_insert=True)

    def record_instruction_activated(self, objective):
        if self._disabled:
            return
        instruction_event = self._get_event_from_instruction_uuid(objective.uuid)
        if instruction_event is None:
            logger.error(
                f"Could not find previous receipt of activated instruction with UUID {objective.uuid}"
            )
            return
        event = EventFromInstructionActivated(
            self._game_record,
            self._turn_number,
            self._tick,
            instruction_event,
            objective.uuid,
        )
        event.save(force_insert=True)

    def record_instruction_complete(self, objective_complete):
        if self._disabled:
            return
        instruction_event = self._get_event_from_instruction_uuid(
            objective_complete.uuid
        )
        if instruction_event is None:
            logger.error(
                f"Could not find previous receipt of activated instruction with UUID {objective_complete.uuid}"
            )
            return
        event = EventFromInstructionDone(
            self._game_record,
            self._turn_number,
            self._tick,
            instruction_event,
            objective_complete.uuid,
        )
        event.save(force_insert=True)

    def record_action(self, action, action_code, position, heading):
        if self._disabled:
            return
        origin = EventOrigin.SERVER
        event = EventFromAction(
            self._game_record,
            self._turn_number,
            self._tick,
            origin,
            action,
            position,
            heading,
            action_code,
        )
        event.save(force_insert=True)

    def record_move(
        self, actor, action: Action, active_instruction, position_before, heading_before
    ):
        if self._disabled:
            return
        instruction_event = None
        if active_instruction is not None:
            instruction_event = self._get_event_from_instruction_uuid(
                active_instruction.uuid
            )
        move_code = self._get_move_code_for_action(actor, action)
        origin = EventOrigin.NONE
        if actor.role() == Role.LEADER:
            origin = EventOrigin.LEADER
        elif actor.role() == Role.FOLLOWER:
            origin = EventOrigin.FOLLOWER
        event = EventFromAction(
            self._game_record,
            self._turn_number,
            self._tick,
            origin,
            action,
            position_before,
            heading_before,
            move_code,
            instruction_event,
        )
        if actor.role == Role.FOLLOWER:
            self._last_follower_move = event
        self._last_move = event
        event.save(force_insert=True)

    def record_live_feedback(self, feedback, follower, active_instruction):
        if self._disabled:
            return
        event = EventFromLiveFeedback(
            self._game_record,
            self._turn_number,
            self._tick,
            feedback,
            follower,
            self._last_follower_move,
        )
        event.save(force_insert=True)

    def record_instruction_cancelled(self, objective):
        if self._disabled:
            return
        instruction_event = self._get_event_from_instruction_uuid(objective.uuid)
        if instruction_event is None:
            logger.warn(f"Could not find instruction record for {objective.uuid}")
            return
        event = EventFromInstructionCancelled(
            self._game_record,
            self._turn_number,
            self._tick,
            instruction_event,
            objective.uuid,
        )
        event.save(force_insert=True)

    def record_start_of_turn(
        self,
        turn_state,
        end_reason,
        turn_skipped: bool = False,
        used_all_moves: bool = False,
        finished_all_commands: bool = False,
    ):
        if self._disabled:
            return
        # Clear at turn end.
        self._last_follower_move = None
        notes = []
        if turn_skipped:
            notes.append("SkippedTurnNoInstructionsTodo")
        if used_all_moves:
            notes.append("UsedAllMoves")
        if finished_all_commands:
            notes.append("FinishedAllCommands")
        notes_string = ",".join(notes)
        short_code = "|".join([end_reason, notes_string])
        event = EventFromStartOfTurn(
            self._game_record, self._tick, turn_state, short_code
        )
        event.save(force_insert=True)

    def record_turn_state(self, turn_state, reason=""):
        if self._disabled:
            return
        self._turn_number = turn_state.turn_number
        short_code = "|".join([reason, ""])
        event = EventFromTurnState(
            self._game_record, self._tick, turn_state, short_code
        )
        event.save(force_insert=True)
        self._game_record.score = turn_state.score
        self._game_record.number_turns = turn_state.turn_number
        self._game_record.save()

    def record_feedback_question(self, feedback_question: FeedbackQuestion):
        if self._disabled:
            return
        event = EventFromFeedbackQuestion(
            self._game_record,
            self._turn_number,
            self._tick,
            feedback_question,
        )
        event.save(force_insert=True)

    def record_feedback_response(self, feedback_response: FeedbackResponse):
        if self._disabled:
            return
        question_event = self._get_event_from_question_uuid(feedback_response.uuid)
        if question_event is None:
            logger.error(
                f"Could not find previous receipt of feedback question with UUID {feedback_response.uuid}"
            )
            return
        event = EventFromFeedbackResponse(
            self._game_record,
            self._turn_number,
            self._tick,
            question_event,
            feedback_response,
        )
        event.save(force_insert=True)

    def record_game_over(self):
        if self._disabled:
            return
        self._game_record.completed = True
        self._game_record.end_time = datetime.utcnow()
        self._game_record.save()

    def kvals(self):
        if self._disabled:
            return None
        if self._game_record.kvals is None:
            return {}
        return orjson.loads(self._game_record.kvals)

    def set_kvals(self, kvals):
        if self._disabled:
            return
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
        )
        return record

    def _get_move_code_for_action(self, actor, action):
        move_code = ""
        forward_location = actor.location().neighbor_at_heading(actor.heading_degrees())
        backward_location = actor.location().neighbor_at_heading(
            actor.heading_degrees() + 180
        )
        new_location = HecsCoord.add(actor.location(), action.displacement)
        if new_location == forward_location:
            move_code = "MF"
        elif new_location == backward_location:
            move_code = "MB"
        elif new_location == actor.location():
            if action.rotation == 60:
                move_code = "TR"
            elif action.rotation == -60:
                move_code = "TL"
            else:
                move_code = "INVALID"
        else:
            move_code = "INVALID"
        return move_code

    def _get_event_from_instruction_uuid(self, instruction_uuid):
        instruction_sent_event_query = Event.select().where(
            Event.type == EventType.INSTRUCTION_SENT,
            Event.short_code == instruction_uuid,
        )
        if not instruction_sent_event_query.exists():
            return None
        return instruction_sent_event_query.get()

    def _get_event_from_question_uuid(self, question_uuid):
        question_event_query = Event.select().where(
            Event.type == EventType.FEEDBACK_QUESTION,
            Event.short_code == question_uuid,
        )
        if not question_event_query.exists():
            return None
        return question_event_query.get()
