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
        tick=tick,
        origin=EventOrigin.SERVER,
        data=JsonSerialize(map_update),
    )


def EventFromInitialState(game, tick: int, leader, follower):
    initial_state = InitialState(
        leader_id=leader.actor_id(),
        follower_id=follower.actor_id(),
        leader_position=leader.location(),
        leader_rotation_degrees=leader.heading_degrees(),
        follower_position=follower.location(),
        follower_rotation_degrees=follower.heading_degrees(),
    )
    return Event(
        game=game,
        type=EventType.INITIAL_STATE,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=JsonSerialize(initial_state),
    )


def EventFromPropUpdate(game, tick: int, prop_update):
    return Event(
        game=game,
        type=EventType.PROP_UPDATE,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=JsonSerialize(prop_update),
    )


def EventFromTurnState(game, tick: int, turn_state, short_code):
    return Event(
        game=game,
        type=EventType.TURN_STATE,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=JsonSerialize(turn_state),
        short_code=short_code,
        role=turn_state.turn,
    )


def EventFromCardSpawn(game, tick: int, card):
    return Event(
        game=game,
        type=EventType.CARD_SPAWN,
        tick=tick,
        origin=EventOrigin.SERVER,
        data=JsonSerialize(card),
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
        data=JsonSerialize(card),
        short_code=short_code,
        location=card.location,
        orientation=card.rotation_degrees,
    )


def EventFromCardSet(
    game, tick: int, origin: EventOrigin, cardset: List[Card], score, last_move
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
        data=JsonSerialize(data),
    )


def EventFromInstructionSent(game, tick: int, instruction):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_SENT,
        tick=tick,
        origin=EventOrigin.LEADER,
        short_code=instruction.uuid,
        data=JsonSerialize(instruction),
    )


def EventFromInstructionActivated(game, tick, instruction_event, uuid):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_ACTIVATED,
        tick=tick,
        origin=EventOrigin.SERVER,
        parent_event=instruction_event,
        short_code=uuid,
    )


def EventFromInstructionDone(game, tick, instruction_event, uuid):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_DONE,
        tick=tick,
        origin=EventOrigin.FOLLOWER,
        role=Role.FOLLOWER,
        parent_event=instruction_event,
        short_code=uuid,
    )


def EventFromInstructionCancelled(game, tick, instruction_event, instruction_uuid):
    return Event(
        game=game,
        type=EventType.INSTRUCTION_CANCELLED,
        tick=tick,
        origin=EventOrigin.LEADER,
        parent_event=instruction_event,
        short_code=instruction_uuid,
    )


def EventFromMove(
    game,
    tick: int,
    origin: EventOrigin,
    action,
    location_before,
    orientation_before,
    instruction_event,
    action_code,
):
    return Event(
        game=game,
        type=EventType.MOVE,
        tick=tick,
        origin=origin,
        parent_event=instruction_event,
        data=JsonSerialize(action),
        location=location_before,
        orientation=orientation_before,
        short_code=action_code,
        role=origin,
    )


def EventFromLiveFeedback(
    game, tick: int, feedback: live_feedback.LiveFeedback, follower, last_move
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
        tick=tick,
        origin=EventOrigin.LEADER,
        role=Role.LEADER,
        parent_event=last_move,
        data=JsonSerialize(feedback),
        short_code=short_code,
        location=follower.location(),
        orientation=follower.heading_degrees(),
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

        if leader is None or follower is None:
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
        event = EventFromCardSpawn(self._game_record, self._tick, card)
        event.save(force_insert=True)

    def record_card_selection(self, actor, card: Card):
        if self._disabled:
            return
        origin = EventOrigin.NONE
        if actor is not None:
            origin = (
                EventOrigin.LEADER
                if actor.role() == Role.LEADER
                else EventOrigin.FOLLOWER
            )
        event = EventFromCardSelect(
            self._game_record, self._tick, origin, card, self._last_move
        )
        event.save(force_insert=True)

    def record_card_set(self, actor, cards: List[Card], score):
        if self._disabled:
            return
        origin = EventOrigin.NONE
        if actor is not None:
            origin = (
                EventOrigin.LEADER
                if actor.role() == Role.LEADER
                else EventOrigin.FOLLOWER
            )
        event = EventFromCardSet(
            self._game_record, self._tick, origin, cards, score, self._last_move
        )
        event.save(force_insert=True)

    def record_instruction_sent(self, objective):
        if self._disabled:
            return
        event = EventFromInstructionSent(self._game_record, self._tick, objective)
        event.save(force_insert=True)

    def record_instruction_activated(self, objective):
        if self._disabled:
            return
        instruction_event = self._get_event_for_instruction_uuid(objective.uuid)
        if instruction_event is None:
            logger.error(
                f"Could not find previous receipt of activated instruction with UUID {objective.uuid}"
            )
            return
        event = EventFromInstructionActivated(
            self._game_record, self._tick, instruction_event, objective.uuid
        )
        event.save(force_insert=True)

    def record_instruction_complete(self, objective_complete):
        if self._disabled:
            return
        instruction_event = self._get_event_for_instruction_uuid(
            objective_complete.uuid
        )
        if instruction_event is None:
            logger.error(
                f"Could not find previous receipt of activated instruction with UUID {objective_complete.uuid}"
            )
            return
        event = EventFromInstructionDone(
            self._game_record, self._tick, instruction_event, objective_complete.uuid
        )
        event.save(force_insert=True)

    def record_move(
        self, actor, action: Action, active_instruction, position_before, heading_before
    ):
        if self._disabled:
            return
        instruction_event = None
        if active_instruction is not None:
            instruction_event = self._get_event_for_instruction_uuid(
                active_instruction.uuid
            )
        move_code = self._get_move_code_for_action(actor, action)
        origin = (
            EventOrigin.LEADER if actor.role() == Role.LEADER else EventOrigin.FOLLOWER
        )
        event = EventFromMove(
            self._game_record,
            self._tick,
            origin,
            action,
            position_before,
            heading_before,
            instruction_event,
            move_code,
        )
        if actor.role == Role.FOLLOWER:
            self._last_follower_move = event
        self._last_move = event
        event.save(force_insert=True)

    def record_live_feedback(self, feedback, follower):
        if self._disabled:
            return
        event = EventFromLiveFeedback(
            self._game_record, self._tick, feedback, follower, self._last_follower_move
        )
        event.save(force_insert=True)

    def record_instruction_cancelled(self, objective):
        if self._disabled:
            return
        instruction_event = self._get_event_for_instruction_uuid(objective.uuid)
        if instruction_event is None:
            logger.warn(f"Could not find instruction record for {objective.uuid}")
            return
        event = EventFromInstructionCancelled(
            self._game_record, self._tick, instruction_event, objective.uuid
        )
        event.save(force_insert=True)

    def record_end_of_turn(
        self,
        turn_state,
        end_reason,
        turn_skipped,
        used_all_moves,
        finished_all_commands,
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
        event = EventFromTurnState(
            self._game_record, self._tick, turn_state, short_code
        )
        event.save(force_insert=True)

    def record_turn_state(self, turn_state, reason=""):
        if self._disabled:
            return
        "|".join([reason, ""])
        event = EventFromTurnState(self._game_record, self._tick, turn_state, reason)
        event.save(force_insert=True)
        self._game_record.score = turn_state.score
        self._game_record.number_turns = turn_state.turn_number
        self._game_record.save()

    def record_game_over(self):
        if self._disabled:
            return
        self._game_record.completed = True
        self._game_record.end_time = datetime.utcnow()
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

    def _get_event_for_instruction_uuid(self, instruction_uuid):
        instruction_sent_event_query = Event.select().where(
            Event.type == EventType.INSTRUCTION_SENT,
            Event.short_code == instruction_uuid,
        )
        if not instruction_sent_event_query.exists():
            return None
        return instruction_sent_event_query.get()
