# Adapted from merge_db.py.
# Migrates the old database schema to the new one.

import bisect
import copy
import logging
import sys
from datetime import datetime, timedelta

import fire
import orjson
import peewee

import server.card as card
import server.messages.live_feedback as live_feedback_msg
import server.messages.prop as prop_msg
import server.messages.turn_state as turn_msg
import server.schemas.defaults as defaults
import server.schemas.util as schema_util
from server.messages.objective import ObjectiveMessage
from server.messages.rooms import Role
from server.schemas import base
from server.schemas.cards import Card, CardSelections, CardSets
from server.schemas.event import Event, EventOrigin, EventType
from server.schemas.game import (
    Game,
    InitialState,
    Instruction,
    LiveFeedback,
    Move,
    Turn,
)
from server.schemas.google_user import GoogleUser
from server.schemas.map import MapUpdate
from server.schemas.mturk import Assignment, Worker, WorkerExperience
from server.schemas.prop import PropUpdate

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


def SwitchToDatabase(db):
    base.SetDatabaseByPath(db)
    base.ConnectDatabase()


TICK_TIME_DELTA = timedelta(milliseconds=5)


def FindMatchingCardProp(prop_update: PropUpdate, candidate: Card):
    # Find the matching card based on location, count, shape, and color.
    matching_card = None
    for prop in prop_update.props:
        card_obj = card.Card.FromProp(prop)
        if (
            card_obj.location == candidate.location
            and card_obj.count == candidate.count
            and str(card_obj.shape) == candidate.shape
            and str(card_obj.color) == candidate.color
        ):
            matching_card = copy.deepcopy(card_obj)
            break
    return matching_card


# TODO For every Event(), make tick = -1 and make sure server_time is populated.
# At the end of this method, sort all generated events and assign a
# monotonically increasing tick value. Cluster based on millisecond. If two
# events are within 1ms of each other, they are the same tick. Assign each event
# a tick number.
def migrate_to_new_game(
    new_db,
    old_game,
    game_moves,
    turn_states,
    instructions,
    live_feedback,
    map_updates,
    card_sets,
    card_selections,
    prop_updates,
    initial_states,
):
    new_game = Game(
        id=old_game.id,
        type=old_game.type,
        log_directory=old_game.log_directory,
        world_seed=old_game.world_seed,
        leader_id=old_game.leader_id,
        follower_id=old_game.follower_id,
        google_leader_id=old_game.google_leader_id,
        google_follower_id=old_game.google_follower_id,
        number_cards=old_game.number_cards,
        score=old_game.score,
        number_turns=old_game.number_turns,
        start_time=old_game.start_time,
        end_time=old_game.end_time,
        completed=old_game.completed,
        valid=old_game.valid,
        who_is_agent=old_game.who_is_agent,
        lead_assignment=old_game.lead_assignment_id
        if old_game.lead_assignment_id != None
        else None,
        follow_assignment=old_game.follow_assignment_id
        if old_game.follow_assignment_id != None
        else None,
        server_software_commit=old_game.server_software_commit,
    )
    new_game.save(force_insert=True)

    map_updates = sorted(map_updates, key=lambda m: m.time)
    game_turns = sorted(turn_states, key=lambda t: t.time)
    map_event = Event(
        game=new_game,
        type=EventType.MAP_UPDATE,
        server_time=map_updates[0].time,
        turn_number=0,
        origin=EventOrigin.SERVER,
        data=map_updates[0].map_data.to_json(),
        tick=-1,
    )
    map_event.save(force_insert=True)

    prop_updates = sorted(prop_updates, key=lambda p: p.time)
    prop_data_in_map_update = False
    if len(prop_updates) > 0:
        prop_event = Event(
            game=new_game,
            type=EventType.PROP_UPDATE,
            server_time=prop_updates[0].time,
            turn_number=0,
            origin=EventOrigin.SERVER,
            data=JsonSerialize(prop_updates[0].prop_data),
            tick=-1,
        )
        prop_event.save(force_insert=True)
    else:
        # Create prop updates from map data.
        prop_data_in_map_update = True
        for map_update in map_updates:
            map_data = map_update.map_data
            props = map_data.props
            prop_update = prop_msg.PropUpdate(props=props)
            # To determine the turn_number, get the most recent turn_state and
            # use its turn_number.
            turn_number = 0
            for turn_state in game_turns:
                if turn_state.time < map_update.time:
                    turn_number = turn_state.turn_number
                else:
                    break
            prop_event = Event(
                game=new_game,
                type=EventType.PROP_UPDATE,
                server_time=map_update.time,
                turn_number=turn_number,
                origin=EventOrigin.SERVER,
                data=JsonSerialize(prop_update),
                tick=-1,
            )
            prop_event.save(force_insert=True)

    card_sets = sorted(card_sets, key=lambda c: c.move.server_time)
    final_turn = game_turns[-1] if game_turns else None
    last_turn = None
    time_per_turn = {}
    for i, turn_state in enumerate(game_turns):
        event_type = EventType.TURN_STATE
        if not last_turn or (last_turn.role != turn_state.role):
            event_type = EventType.START_OF_TURN
        moves_remaining = 10 if turn_state.role == Role.LEADER else 5
        move_times = [c.move.server_time for c in card_sets]
        last_score_i = bisect.bisect(move_times, turn_state.time)
        last_score = 0
        if last_score_i > 0:
            last_score = card_sets[last_score_i - 1].score
        elif len(card_sets) > 0:
            last_score = card_sets[0].score
        if turn_state.role not in [Role.LEADER, Role.FOLLOWER]:
            if i < len(game_turns) - 1:
                next_turn_state = game_turns[i + 1]
                # If any moves between now and the next turn state are
                # leader moves, then we are the leader.
                if any(
                    m.character_role == "Role.LEADER"
                    for m in game_moves
                    if m.server_time >= turn_state.time
                    and m.server_time < next_turn_state.time
                ):
                    turn_state.role = Role.LEADER
                elif any(
                    m.character_role == "Role.FOLLOWER"
                    for m in game_moves
                    if m.server_time >= turn_state.time
                    and m.server_time < next_turn_state.time
                ):
                    turn_state.role = Role.FOLLOWER
            if turn_state.role not in [Role.LEADER, Role.FOLLOWER]:
                # Check for instructions. If any were made by the leader,
                # then we are the leader.
                if (
                    len(
                        [
                            instr
                            for instr in instructions
                            if instr.time >= turn_state.time
                        ]
                    )
                    > 0
                ):
                    turn_state.role = Role.LEADER
            # The following end_method strings indicate that its now the leader's turn.
            if "FollowerOutOfMoves" in turn_state.end_method:
                turn_state.role = Role.LEADER
            if "FollowerFinishedInstructions" in turn_state.end_method:
                turn_state.role = Role.LEADER
            if "UserPromptedInterruption":
                turn_state.role = Role.LEADER
            if turn_state.role not in [Role.LEADER, Role.FOLLOWER]:
                logger.error(
                    f"---- Unable to recover role for turn state {turn_state}."
                )
                logger.error(f"Turn state end_method: {turn_state.end_method}")
                logger.error(f"Turn state notes: {turn_state.notes}")
                turn_state.role = Role.NONE
        turn_state_obj = turn_msg.TurnState(
            turn_state.role,
            moves_remaining,
            final_turn.turn_number - turn_state.turn_number if final_turn else 0,
            datetime.max,
            old_game.start_time,
            last_score,
            last_score,
            i == len(game_turns) - 1,
            turn_state.turn_number,
        )
        if turn_state.turn_number not in time_per_turn:
            time_per_turn[turn_state.turn_number] = turn_state.time
        elif turn_state.time < time_per_turn[turn_state.turn_number]:
            time_per_turn[turn_state.turn_number] = turn_state.time
        event = Event(
            game=new_game,
            type=event_type,
            role=turn_state.role
            if turn_state.role in [Role.LEADER, Role.FOLLOWER]
            else Role.NONE,
            turn_number=turn_state.turn_number,
            server_time=turn_state.time,
            origin=EventOrigin.SERVER,
            data=JsonSerialize(turn_state_obj),
            short_code="",
            tick=-1,
        )
        event.save(force_insert=True)
        last_turn = turn_state

    initial_states = sorted(initial_states, key=lambda i: i.time)
    initial_state_obj = None
    initial_state_time = datetime.min
    if len(initial_states) == 0:
        # Get it from the position_before and orientation_before fields of the first actions for each role.
        leader_move = [
            move for move in game_moves if move.character_role == Role.LEADER
        ]
        follower_move = [
            move for move in game_moves if move.character_role == Role.FOLLOWER
        ]
        if len(leader_move) == 0 or len(follower_move) == 0:
            logger.warn(f"Unable to recover initial state for game {old_game.id}")
            raise ValueError("Unable to recover initial state.")
        else:
            first_leader_move = leader_move[0]
            first_follower_move = follower_move[0]
            initial_state_time = old_game.start_time
            initial_state = schema_util.InitialState(
                leader_id=first_leader_move.action.id,
                follower_id=first_follower_move.action.id,
                leader_position=first_leader_move.position_before,
                leader_rotation=first_leader_move.orientation_before,
                follower_position=first_follower_move.position_before,
                follower_rotation=first_follower_move.orientation_before,
            )
    else:
        initial_state = initial_states[0]
        initial_state_obj = schema_util.InitialState(
            leader_id=initial_state.leader_id,
            follower_id=initial_state.follower_id,
            leader_position=initial_state.leader_position,
            leader_rotation_degrees=initial_state.leader_rotation_degrees,
            follower_position=initial_state.follower_position,
            follower_rotation_degrees=initial_state.follower_rotation_degrees,
        )
        initial_state_time = old_game.start_time
    if initial_state_obj:
        initial_state_event = Event(
            game=new_game,
            type=EventType.INITIAL_STATE,
            server_time=initial_state_time,
            turn_number=0,
            origin=EventOrigin.SERVER,
            data=JsonSerialize(initial_state_obj),
            tick=-1,
        )
        initial_state_event.save(force_insert=True)

    game_instructions = sorted(instructions, key=lambda i: i.time)
    game_moves = sorted(game_moves, key=lambda m: m.server_time)
    game_card_selections = sorted(card_selections, key=lambda s: s.game_time)
    game_card_sets = sorted(card_sets, key=lambda s: s.move.server_time)
    event_per_i_uuid = {}

    # Traverse instructions backwards. Propagate cancellations back to instructions that were marked as neither DONE nor CANCELLED.
    for i in range(len(game_instructions) - 1, -1, -1):
        instruction = game_instructions[i]
        if instruction.turn_cancelled != -1:
            for j in range(i - 1, -1, -1):
                prev_instruction = game_instructions[j]
                if (
                    prev_instruction.turn_cancelled == -1
                    and prev_instruction.turn_completed == -1
                ):
                    prev_instruction.turn_cancelled = instruction.turn_cancelled

    for instr_index, instruction in enumerate(game_instructions):
        instr_sent_event = Event(
            game=new_game,
            type=EventType.INSTRUCTION_SENT,
            server_time=instruction.time,
            turn_number=instruction.turn_issued,
            origin=EventOrigin.LEADER,
            role="Role.LEADER",
            data=ObjectiveMessage(
                Role.LEADER, instruction.text, instruction.uuid, False, False
            ).to_json(),
            short_code=instruction.uuid,
            tick=-1,
        )
        instr_sent_event.save(force_insert=True)
        event_per_i_uuid[instruction.uuid] = instr_sent_event
        event_moves = sorted(
            [
                (i, move)
                for i, move in enumerate(game_moves)
                if move.instruction == instruction
            ],
            key=lambda m: m[1].server_time,
        )
        if len(event_moves) > 0:
            (_, event_first_move) = event_moves[0]
            (last_move_index, event_last_move) = event_moves[-1]
        else:
            (_, event_first_move) = -1, None
            (last_move_index, event_last_move) = -1, None

        # We need to recreate the instruction activation timestamp here,
        # since the old database didn't store it accurately.
        #
        # To determine when an instruction is activated, we take the maximum of:
        # - When the previous instruction was completed or cancelled.
        # - When the current instruction was sent.
        #
        # We also check if the instruction was activated. It will always be except in these two cases:
        # 1. The instruction was cancelled before it was activated. This can be detected by checking if the instruction was cancelled
        #    within TIME_TICK_DELTA of the previous instruction.
        # 2. The instruction was unactivated at the end of the game. This can be detected by checking if the previous instruction was
        #    cancelled or completed, implying that this was activated.
        time_activated = instr_sent_event.server_time + TICK_TIME_DELTA
        instruction_activated = True  # Assume it was activated.
        activation_event = None
        if instr_index >= 1:
            previous_instruction = game_instructions[instr_index - 1]
            last_instr_finished_query = Event.select().where(
                Event.short_code == previous_instruction.uuid,
                Event.type
                << [EventType.INSTRUCTION_DONE, EventType.INSTRUCTION_CANCELLED],
            )
            if last_instr_finished_query.exists():
                activation_event = last_instr_finished_query.get()
                time_activated = max(
                    time_activated, activation_event.server_time + TICK_TIME_DELTA
                )
                # If this and the previous instruction were cancelled in the same turn, then this instruction was never activated.
                if (
                    previous_instruction.turn_cancelled == instruction.turn_cancelled
                ) and (previous_instruction.turn_cancelled != -1):
                    instruction_activated = False
            else:
                instruction_activated = False
        if instruction_activated:
            instr_activated_event = Event(
                game=new_game.id,
                type=EventType.INSTRUCTION_ACTIVATED,
                server_time=time_activated,
                turn_number=event_first_move.turn_number
                if event_first_move
                else instr_sent_event.turn_number,
                origin=EventOrigin.SERVER,
                role="Role.FOLLOWER",
                parent_event=instr_sent_event.id,
                short_code=instruction.uuid,
                tick=-1,
            )
            instr_activated_event.save(force_insert=True)
        if instruction.turn_completed != -1:
            # We need to recreate the instruction DONE timestamp here, since
            # the old database didn't store it accurately.
            #
            # To determine when an instruction is complete, we take the maximum of:
            # - When the instruction was activated (worst-case minimum bound)
            # - The last move of the instruction.
            # - Card selections immediately following that move, if available.
            # - Card sets immediately following that move, if available.
            #
            # Immediate means that they follow after the move, but before
            # any subsequent moves.
            if not instruction_activated:  # Quick assertion.
                # It was found that some instructions were marked as completed
                # but not activated. This is an error. Fortunately it didn't
                # happen in any trial games, must just be debug data.
                # Mark game as invalid and return.
                new_game.valid = False
                new_game.save()
                return
            time_done = instr_activated_event.server_time + TICK_TIME_DELTA
            if event_last_move:
                time_done = max(time_done, event_last_move.server_time)

                last_move_time = event_last_move.server_time
                next_move_time = datetime.max
                if len(game_moves) > last_move_index + 1:
                    next_move_time = game_moves[last_move_index + 1].server_time

                immediate_following_selections = [
                    selection
                    for selection in game_card_selections
                    if last_move_time <= selection.game_time < next_move_time
                ]
                if len(immediate_following_selections) != 0:
                    time_done = max(
                        time_done, immediate_following_selections[0].game_time
                    )

                immediate_following_sets = [
                    s
                    for s in game_card_sets
                    if last_move_time <= s.move.server_time < next_move_time
                ]
                if len(immediate_following_sets) != 0:
                    time_done = max(
                        time_done, immediate_following_sets[0].move.server_time
                    )
            # Use event INSTRUCTION_DONE for newer games
            instr_done_event = Event(
                game=new_game,
                type=EventType.INSTRUCTION_DONE,
                server_time=time_done,
                turn_number=event_last_move.turn_number
                if event_last_move
                else instr_sent_event.turn_number,
                origin=EventOrigin.FOLLOWER,
                role="Role.FOLLOWER",
                short_code=instruction.uuid,
                parent_event=instr_sent_event.id,
                tick=-1,
            )
            instr_done_event.save(force_insert=True)
        elif instruction.turn_cancelled != -1:
            # We need to recreate the instruction CANCELLED timestamp here, since
            # the old database didn't store it accurately.
            #
            # To determine when an instruction is cancelled, we take the maximum of:
            # - When the instruction was activated (worst-case minimum bound)
            # - If the instruction was not activated, then when the previous instruction was cancelled.
            # - The last move of the instruction.
            # - If the next instruction was not activated (cancelled simultaneously with this one), then when the next instruction was sent.
            #     Note that this is actually done on the next iteration, and it retroactively sets the cancelled timestamp.
            if instruction_activated:
                time_cancelled = instr_activated_event.server_time + TICK_TIME_DELTA
            else:
                assert (
                    instr_index > 0
                ), "The first instruction is always activated instantly. Somehow this instruction was not activated."
                # This instruction was cancelled at the same time as several
                # other instructions. Find them by querying for instructions
                # with the same turn_cancelled.
                previous_instruction = game_instructions[instr_index - 1]
                previous_instruction_query = Event.select().where(
                    Event.type == EventType.INSTRUCTION_CANCELLED,
                    Event.short_code == previous_instruction.uuid,
                )
                assert (
                    previous_instruction_query.exists()
                ), "The previous instruction was not cancelled. How did this instruction get cancelled?"

                previous_instr_cancelled_event = previous_instruction_query.get()
                previous_instr_cancelled_event.server_time

                cancelled_instructions = [
                    i
                    for i in game_instructions
                    if i.turn_cancelled == instruction.turn_cancelled
                ]
                assert (
                    len(cancelled_instructions) > 1
                ), "The previous instruction was not cancelled. How did this instruction get cancelled?"
                # All instructions that were cancelled simultaneously with this one.
                # Okay, now to figure out the time cancelled, we have to
                # compare the time that this instruction was sent (known)
                # and the time that the simultaneous instructions were cancelled.
                time_cancelled = (
                    max(
                        [previous_instr_cancelled_event.server_time]
                        + [i.time for i in cancelled_instructions]
                    )
                    + TICK_TIME_DELTA
                )
            if event_last_move:
                time_cancelled = max(time_cancelled, event_last_move.server_time)
            instr_cancelled_event = Event(
                game=new_game,
                type=EventType.INSTRUCTION_CANCELLED,
                server_time=time_cancelled,
                turn_number=instruction.turn_cancelled,
                origin=EventOrigin.LEADER,
                role="Role.LEADER",
                short_code=instruction.uuid,
                parent_event=instr_sent_event.id,
                tick=-1,
            )
            instr_cancelled_event.save(force_insert=True)

    for move in game_moves:
        origin = (
            EventOrigin.LEADER
            if move.character_role == "Role.LEADER"
            else EventOrigin.FOLLOWER
        )
        # Generate an event from the move.
        move_event = Event(
            game=new_game,
            type=EventType.ACTION,
            server_time=move.server_time,
            origin=origin,
            role=move.character_role,
            # parent_event
            parent_event=event_per_i_uuid[move.instruction.uuid].id
            if move.instruction is not None
            else None,
            short_code=move.action_code,
            data=JsonSerialize(move.action),
            location=move.position_before,
            orientation=move.orientation_before,
            tick=-1,
        )
        move_event.save(force_insert=True)

    game_feedback = sorted(live_feedback, key=lambda f: f.server_time)
    for feedback in game_feedback:
        last_move = (
            Event.select()
            .where(
                Event.game == new_game,
                Event.origin == EventOrigin.FOLLOWER,
                Event.type == EventType.ACTION,
                Event.server_time < feedback.server_time,
            )
            .order_by(Event.server_time.desc())
            .first()
        )
        feedback_data = live_feedback_msg.LiveFeedback(
            live_feedback_msg.FeedbackType[feedback.feedback_type]
        )
        short_code = ""
        if feedback_data.signal == live_feedback_msg.FeedbackType.POSITIVE:
            short_code = "Positive"
        elif feedback_data.signal == live_feedback_msg.FeedbackType.NEGATIVE:
            short_code = "Negative"
        elif feedback_data.signal == live_feedback_msg.FeedbackType.NONE:
            short_code = "None"
        event = Event(
            server_time=feedback.server_time,
            game=new_game,
            type=EventType.LIVE_FEEDBACK,
            turn_number=feedback.turn_number,
            origin=EventOrigin.LEADER,
            role="Role.LEADER",
            parent_event=last_move,
            data=JsonSerialize(feedback_data),
            short_code=short_code,
            location=feedback.follower_position,
            orientation=feedback.follower_orientation,
            tick=-1,
        )
        event.save(force_insert=True)

    game_prop_updates = prop_updates
    for i, prop_update in enumerate(game_prop_updates):
        # First prop update is captured above.
        if i == 0:
            continue
        prop_data = prop_update.prop_data
        last_prop_data = game_prop_updates[i - 1].prop_data
        new_prop_ids = set([p.id for p in prop_data.props]) - set(
            [p.id for p in last_prop_data.props]
        )
        # last_turn_state = (
        #     game_turns.where(Turn.game == old_game, Turn.time <= prop_update.time)
        #     .order_by(Turn.time.desc())
        #     .first()
        # )
        turn_times = [t.time for t in game_turns]
        last_turn_state_i = bisect.bisect(turn_times, prop_update.time)
        last_turn_state = None
        if last_turn_state_i > 0:
            last_turn_state = game_turns[last_turn_state_i - 1]
        elif len(game_turns) > 0:
            last_score = game_turns[0]
        for prop in prop_data.props:
            if prop.id not in new_prop_ids:
                continue
            card_obj = card.Card.FromProp(prop)
            short_code = " ".join(
                [str(card_obj.count), str(card_obj.color), str(card_obj.shape)]
            )
            prop_event = Event(
                game=new_game,
                type=EventType.CARD_SPAWN,
                server_time=prop_update.time,
                turn_number=last_turn_state.turn_number if last_turn_state else 0,
                origin=EventOrigin.SERVER,
                data=JsonSerialize(card_obj),
                short_code=short_code,
                location=card_obj.location,
                orientation=card_obj.rotation_degrees,
                tick=-1,
            )
            prop_event.save(force_insert=True)

    for selection in game_card_selections:
        origin = (
            EventOrigin.LEADER
            if selection.move.character_role == "Role.LEADER"
            else EventOrigin.FOLLOWER
        )
        # Even though it's called game_time, game_time is populated with
        # utcnow (as if it's server_time), making the name a misnomer.
        move_events = (
            Event.select()
            .where(
                Event.game == new_game,
                Event.type == EventType.ACTION,
                Event.server_time <= selection.game_time,
            )
            .order_by(Event.server_time, Event.server_time.desc())
        )

        # To get the card ID, we need to search the next prop update by timestamp.
        # Then we find the matching card based on location, count, shape, and color.
        # Then we find the card's ID from the prop update.

        # Find the next prop update with a timestamp less than selection.game_time.
        prop_update = None
        if not prop_data_in_map_update:
            # Search previous prop updates.
            prop_update_times = [p.time for p in prop_updates]
            prop_update_index = bisect.bisect(prop_update_times, selection.game_time)
            if prop_update_index < 0:
                logger.info(
                    f"Couldn't find prop update for selection {selection} at time {selection.game_time}. Quitting."
                )
                import sys

                sys.exit(1)
            if prop_update_index == len(prop_updates):
                # Use the previous prop update.
                prop_update_index -= 1
            prop_update = prop_updates[prop_update_index]
        else:
            # Search previous map updates for prop data.
            map_update_times = [m.time for m in map_updates]
            map_update_index = bisect.bisect(map_update_times, selection.game_time)
            if map_update_index < 0:
                logger.info(
                    f"Couldn't find map update for selection {selection} at time {selection.game_time}. Quitting."
                )
                import sys

                sys.exit(1)
            if map_update_index == len(map_updates):
                # Use the previous map update.
                map_update_index -= 1
            map_update = map_updates[map_update_index]
            prop_update = prop_msg.PropUpdate(map_update.map_data.props)

        # Find the matching card based on location, count, shape, and color.
        matching_card = None
        if not prop_data_in_map_update:
            list_of_props = prop_update.prop_data.props
        else:
            list_of_props = prop_update.props
        for prop in list_of_props:
            card_obj = card.Card.FromProp(prop)
            if (
                card_obj.location == selection.card.location
                and card_obj.count == selection.card.count
                and str(card_obj.shape) == selection.card.shape
                and str(card_obj.color) == selection.card.color
            ):
                matching_card = copy.deepcopy(card_obj)
                break
        if matching_card is None:
            # Use the previous prop update.
            if prop_data_in_map_update:
                prop_update = prop_msg.PropUpdate(
                    map_updates[map_update_index - 1].map_data.props
                )
                # Named this prop_list to avoid shadowing list_of_props.
                prop_list = prop_update.props
            else:
                prop_update = prop_updates[prop_update_index - 1]
                # Named this prop_list to avoid shadowing list_of_props.
                prop_list = prop_update.prop_data.props
            for prop in prop_list:
                card_obj = card.Card.FromProp(prop)
                if (
                    card_obj.location == selection.card.location
                    and card_obj.count == selection.card.count
                    and str(card_obj.shape) == selection.card.shape
                    and str(card_obj.color) == selection.card.color
                ):
                    matching_card = copy.deepcopy(card_obj)
                    break
        if matching_card is None:
            logger.info(
                f"Couldn't find card for selection {selection} at time {selection.game_time}. Quitting."
            )
            import sys

            sys.exit(1)

        matching_card.selected = selection.type == "select"
        event = Event(
            game=new_game,
            type=EventType.CARD_SELECT,
            turn_number=selection.move.turn_number,
            server_time=selection.game_time,
            origin=origin,
            role=selection.move.character_role,
            parent_event=move_event,
            data=JsonSerialize(matching_card),
            short_code=selection.type,
            location=selection.card.location,
            orientation=0,
            tick=-1,
        )
        event.save(force_insert=True)

    for i, card_set in enumerate(game_card_sets):
        origin = (
            EventOrigin.LEADER
            if card_set.move.character_role == "Role.LEADER"
            else EventOrigin.FOLLOWER
        )
        move_event_query = (
            Event.select()
            .where(
                Event.game == new_game,
                Event.type == EventType.ACTION,
                Event.server_time <= card_set.move.server_time,
            )
            .order_by(Event.server_time.desc())
        )
        if move_event_query.count() == 0:
            logger.error(
                f"Could not find move event for card set {card_set.move.server_time} {card_set.move.turn_number}"
            )
            import sys

            sys.exit()
        move_event = move_event_query.get()

        # To get the card, we need to search the next prop update by timestamp.
        # Then we find the matching card based on location, count, shape, and color.
        # Then we find the card's ID from the prop update.

        # Search for the most recent prop update with a timestamp less than card_set.move.server_time.
        if not prop_data_in_map_update:
            prop_update_times = [p.time for p in prop_updates]
            prop_update_index = bisect.bisect(
                prop_update_times, card_set.move.server_time
            )
            prop_update = prop_updates[prop_update_index - 1]
            current_list_of_props = prop_update.prop_data.props
        else:
            map_update_times = [m.time for m in map_updates]
            map_update_index = bisect.bisect(
                map_update_times, card_set.move.server_time
            )
            prop_update = prop_msg.PropUpdate(
                map_updates[map_update_index - 1].map_data.props
            )
            current_list_of_props = prop_update.props
        set_card_locations = []
        # Compare the next and previous prop updates to find the card that was gathered (removed) in the set.
        for prop in current_list_of_props:
            card_obj = card.Card.FromProp(prop)
            set_card_locations.append(card_obj.location)

        # Remove cards from the next prop update.
        if not prop_data_in_map_update:
            next_prop_update = prop_updates[prop_update_index]
            next_prop_list = next_prop_update.prop_data.props
        else:
            if map_update_index == len(map_updates):
                print(
                    f"At last map update. Time: {map_updates[map_update_index - 1].time}"
                )
                print(f"Card set time: {card_set.move.server_time}")
                print(f"Using card selections to determine cards instead.")
                # Let's use card selection times. Get all card selections since
                card_selections = [
                    card
                    for card in game_card_selections
                    if card.move.server_time > game_card_sets[i - 1].move.server_time
                ]
                set_card_locations = []
                for card_selection in card_selections:
                    location = card_selection.card.location
                    if card_selection.type == "select":
                        set_card_locations.append(location)
                    else:
                        set_card_locations.remove(location)
                # Don't iterate over next_prop_list. We already populated set_card_locations.
                next_prop_list = []
                assert (
                    len(set_card_locations) == 3
                ), f"Expected 3 cards at set completion, got {len(set_card_locations)}. game: {new_game.id}"
            else:
                next_map_update = map_updates[map_update_index]
                next_prop_update = prop_msg.PropUpdate(next_map_update.map_data.props)
                next_prop_list = next_prop_update.props
        for prop in next_prop_list:
            card_obj = card.Card.FromProp(prop)
            if card_obj.location in set_card_locations:
                set_card_locations.remove(card_obj.location)

        # Get the cards that were gathered in the set.
        set_cards = []
        for prop in current_list_of_props:
            card_obj = card.Card.FromProp(prop)
            if card_obj.location in set_card_locations:
                set_cards.append(card_obj)

        assert (
            len(set_cards) == 3
        ), f"Expected 3 cards at set completion, got {len(set_cards)}. game: {new_game.id} card_set: {card_set.id}"
        data = {
            "cards": set_cards,
            "score": card_set.score - 1,
        }
        card_set_event = Event(
            game=new_game,
            type=EventType.CARD_SET,
            server_time=card_set.move.server_time,
            turn_number=card_set.move.turn_number,
            origin=origin,
            data=JsonSerialize(data),
            parent_event=move_event,
            short_code=card_set.score,
            tick=-1,
        )
        card_set_event.save(force_insert=True)

    # Now iterate over all the created events in order of server_time. Assign a monotonically increasing tick. If two events occurred within 5ms of each other, assign them the same tick.
    # Do the same for turn_number, catching up if the turn_number is non-null.
    tick = 0
    last_event_time = datetime.min
    last_turn_number = 0
    for event in (
        Event.select().where(Event.game == new_game).order_by(Event.server_time)
    ):
        if (
            event.server_time - last_event_time
        ) >= TICK_TIME_DELTA and last_event_time != datetime.min:
            tick += 1
        event.tick = tick
        if event.turn_number is not None and event.turn_number > last_turn_number:
            last_turn_number = event.turn_number
        else:
            event.turn_number = last_turn_number
        event.save()
        last_event_time = event.server_time


def main(old_db_path, new_db_path, min_game_id=2000):
    logging.basicConfig(level=logging.INFO)
    SwitchToDatabase(old_db_path)
    old_db = base.GetDatabase()

    old_assignments = []
    old_workers = []
    old_google_users = []
    old_games = []
    old_turns = {}
    old_instructions = {}
    old_moves = {}
    old_live_feedback = {}
    old_maps = {}
    old_props = {}
    old_card_sets = {}
    old_card_selections = {}
    old_initial_states = {}

    print(f"Loading data from {old_db_path}...")
    if min_game_id != -1:
        print(
            f"//////////////// WARNING: Only migrating games with id > {min_game_id} ////////////////"
        )
    with old_db.connection_context():
        # Query all games.
        print(f"Querying all games...")
        old_games = list(
            Game.select()
            .join(
                Worker,
                join_type=peewee.JOIN.LEFT_OUTER,
                on=((Game.leader == Worker.id) or (Game.follower == Worker.id)),
            )
            .join(
                Assignment,
                on=(
                    (Game.lead_assignment == Assignment.id)
                    or (Game.follow_assignment == Assignment.id)
                ),
                join_type=peewee.JOIN.LEFT_OUTER,
            )
            .where(Game.id > min_game_id)
            .order_by(Game.id)
        )

        print(f"Querying all instructions...")
        for instruction in Instruction.select().where(
            Instruction.game_id > min_game_id
        ):
            if instruction.game_id not in old_instructions:
                old_instructions[instruction.game_id] = []
            old_instructions[instruction.game_id].append(instruction)

        # Query all moves.
        print(f"Querying all moves...")
        for move in (
            Move.select()
            .where(Move.game_id > min_game_id)
            .join(Instruction, join_type=peewee.JOIN.LEFT_OUTER)
            .select()
        ):
            if move.game_id not in old_moves:
                old_moves[move.game_id] = []
            if move.instruction:
                move.instruction = move.instruction
            old_moves[move.game_id].append(move)

        # Query all live feedback.
        print(f"Querying all live feedback...")
        for live_feedback in (
            LiveFeedback.select()
            .join(Instruction, join_type=peewee.JOIN.LEFT_OUTER)
            .where(LiveFeedback.game_id > min_game_id)
        ):
            if live_feedback.game_id not in old_live_feedback:
                old_live_feedback[live_feedback.game_id] = []
            live_feedback.instruction = live_feedback.instruction
            old_live_feedback[live_feedback.game_id].append(live_feedback)

        # Query all maps.
        print(f"Querying all maps...")
        for map_update in (
            MapUpdate.select()
            .where(MapUpdate.game_id > min_game_id)
            .join(Game)
            .select()
        ):
            if map_update.game_id not in old_maps:
                old_maps[map_update.game_id] = []
            map_update.game = map_update.game
            old_maps[map_update.game_id].append(map_update)

        print(f"Querying all prop updates...")
        for prop_update in (
            PropUpdate.select()
            .join(Game)
            .select()
            .where(PropUpdate.game_id > min_game_id)
        ):
            if prop_update.game_id not in old_props:
                old_props[prop_update.game_id] = []
            prop_update.game = prop_update.game
            old_props[prop_update.game_id].append(prop_update)

        # Query all card selections.
        print(f"Querying all card selections...")
        for card_selection in (
            CardSelections.select()
            .join(Move)
            .switch(CardSelections)
            .join(Card)
            .select()
            .where(CardSelections.game_id > min_game_id)
        ):
            if card_selection.game_id not in old_card_selections:
                old_card_selections[card_selection.game_id] = []
            card_selection.move = card_selection.move
            card_selection.card = card_selection.card
            old_card_selections[card_selection.game_id].append(card_selection)

        print(f"Querying all turns...")
        for turn in Turn.select().join(Game).select().where(Turn.game_id > min_game_id):
            if turn.game_id not in old_turns:
                old_turns[turn.game_id] = []
            turn.game = turn.game
            old_turns[turn.game_id].append(turn)

        print(f"Querying all initial states...")
        for init_state in (
            InitialState.select()
            .join(Game)
            .select()
            .where(InitialState.game_id > min_game_id)
        ):
            if init_state.game_id not in old_initial_states:
                old_initial_states[init_state.game_id] = []
            init_state.game = init_state.game
            old_initial_states[init_state.game_id].append(init_state)

        # Query all card sets.
        set([])
        print(f"Querying all cardsets...")
        for card_set in (
            CardSets.select().join(Move).select().where(CardSets.game_id > min_game_id)
        ):
            if card_set.game_id not in old_card_sets:
                old_card_sets[card_set.game_id] = []
            card_set.move = card_set.move
            old_card_sets[card_set.game_id].append(card_set)

        print(f"Querying assignments...")
        old_assignments = Assignment.select()
        print(f"Querying workers...")
        old_workers = Worker.select()
        print(f"Querying worker experience...")
        old_worker_experience = list(WorkerExperience.select())
        print(f"Querying google users...")
        old_google_users = list(GoogleUser.select())

    # Filter out tutorial games.
    valid_old_games = [game for game in old_games if game.type]
    non_tutorial_old_games = [
        game for game in valid_old_games if "tutorial" not in game.type
    ]
    logger.info(f"Non tutorial games: {len(non_tutorial_old_games)}")

    # We've queried all tables. Print the size of each table.
    logger.info(f"Assignments: {len(old_assignments)}")
    logger.info(f"Workers: {len(old_workers)}")
    logger.info(f"Google Users: {len(old_google_users)}")
    logger.info(f"Worker Experience: {len(old_worker_experience)}")
    logger.info(f"Games: {len(old_games)}")
    logger.info(f"Turns: {len(old_turns)}")
    logger.info(f"Instructions: {len(old_instructions)}")
    logger.info(f"Moves: {len(old_moves)}")
    logger.info(f"Live Feedback: {len(old_live_feedback)}")
    logger.info(f"Maps: {len(old_maps)}")
    logger.info(f"Card Sets: {len(old_card_sets.values())}")
    logger.info(f"Card Selections: {len(old_card_selections)}")
    logger.info(f"Initial States: {len(old_initial_states)}")

    # Log each game on its own line and confirm that we should continue the
    # merge. Print the number of games too.
    logger.info(f"Found {len(old_games)} games in {old_db}")
    if input("Continue? (y/n)") != "y":
        sys.exit(1)

    print(f"Creating new database at {new_db_path}...")
    SwitchToDatabase(new_db_path)
    new_db = base.GetDatabase()
    base.CreateTablesIfNotExists(defaults.ListDefaultTables())

    # Migrate all the workers, assignments, google users.
    print(f"Creating misc tables...")
    for worker_experience in old_worker_experience:
        worker_experience.save(force_insert=True)

    for worker in old_workers:
        worker.save(force_insert=True)

    for assignment in old_assignments:
        assignment.save(force_insert=True)

    for google_user in old_google_users:
        google_user.save(force_insert=True)

    # Migrate all the games.
    with new_db.connection_context():
        for game in non_tutorial_old_games:
            if game.id not in old_maps:
                print(
                    f"Game {game.id} has no map! type: {game.type} score: {game.score}"
                )
                assert game.score == 0
                continue
            print(f"Migrating game {game.id}/{len(old_games)}...")
            with new_db.atomic() as transaction:
                try:
                    migrate_to_new_game(
                        new_db,
                        game,
                        old_moves.get(game.id, []),
                        old_turns.get(game.id, []),
                        old_instructions.get(game.id, []),
                        old_live_feedback.get(game.id, []),
                        old_maps.get(game.id, []),
                        old_card_sets.get(game.id, []),
                        old_card_selections.get(game.id, []),
                        old_props.get(game.id, []),
                        old_initial_states.get(game.id, []),
                    )
                except ValueError as e:
                    transaction.rollback()
                    print(f"Error migrating game {game.id}: {e}")
                    continue

    # Make sure we didn't leave any -1 ticks.
    for event in Event.select():
        if event.tick == -1:
            logger.error(f"Event {event.id.hex} has tick -1!")

    logging.info("Done!")

    # Close the database.
    base.CloseDatabase()


if __name__ == "__main__":
    fire.Fire(main)
