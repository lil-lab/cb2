# Adapted from merge_db.py.
# Migrates the old database schema to the new one.

import bisect
import logging
import sys
from datetime import datetime

import fire
import orjson
import peewee

import server.card as card
import server.messages.live_feedback as live_feedback_msg
import server.messages.turn_state as turn_msg
import server.schemas.defaults as defaults
import server.schemas.util as schema_util
from server.messages.objective import ObjectiveMessage
from server.messages.rooms import Role
from server.schemas import base
from server.schemas.cards import Card, CardSelections, CardSets
from server.schemas.clients import Remote
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
from server.schemas.leaderboard import Leaderboard, Username
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
    with new_db.connection_context():
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

        game_turns = sorted(turn_states, key=lambda t: t.time)
        card_sets = sorted(card_sets, key=lambda c: c.move.server_time)
        final_turn = game_turns[-1] if game_turns else None
        last_turn = None
        time_per_turn = {}
        for i, turn_state in enumerate(game_turns):
            event_type = EventType.TURN_STATE
            if not last_turn or (last_turn.role != turn_state.role):
                event_type = EventType.START_OF_TURN
            moves_remaining = 10 if turn_state.role == Role.LEADER else 5
            last_score_i = bisect.bisect(
                card_sets, turn_state.time, key=lambda c: c.move.server_time
            )
            last_score = 0
            if last_score_i > 0:
                last_score = card_sets[last_score_i - 1].score
            elif len(card_sets) > 0:
                last_score = card_sets[0].score
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
                turn_number=turn_state.turn_number,
                server_time=turn_state.time,
                origin=EventOrigin.SERVER,
                data=JsonSerialize(turn_state_obj),
                short_code="",
                role=turn_state.role,
                tick=-1,
            )
            last_turn = turn_state

        initial_states = sorted(initial_states, key=lambda i: i.time)
        initial_state = initial_states[0]
        initial_state_obj = schema_util.InitialState(
            leader_id=initial_state.leader_id,
            follower_id=initial_state.follower_id,
            leader_position=initial_state.leader_position,
            leader_rotation_degrees=initial_state.leader_rotation_degrees,
            follower_position=initial_state.follower_position,
            follower_rotation_degrees=initial_state.follower_rotation_degrees,
        )
        initial_state_event = Event(
            game=new_game,
            type=EventType.INITIAL_STATE,
            server_time=initial_state.time,
            turn_number=0,
            origin=EventOrigin.SERVER,
            data=JsonSerialize(initial_state_obj),
            tick=-1,
        )
        initial_state_event.save(force_insert=True)

        game_instructions = sorted(instructions, key=lambda i: i.time)
        game_moves = sorted(game_moves, key=lambda m: m.server_time)
        event_per_i_uuid = {}
        for instruction in game_instructions:
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
                [move for move in game_moves if move.instruction == instruction],
                key=lambda m: m.server_time,
            )
            event_first_move = event_moves[0] if len(event_moves) > 0 else None
            event_last_move = event_moves[-1] if len(event_moves) > 0 else None
            instr_activated_event = Event(
                game=new_game.id,
                type=EventType.INSTRUCTION_ACTIVATED,
                server_time=event_first_move.server_time
                if event_first_move
                else instr_sent_event.server_time,
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
                time_done = datetime.max
                if instruction.turn_completed in time_per_turn:
                    time_done = time_per_turn
                if event_last_move and event_last_move.server_time > time_done:
                    time_done = event_last_move.server_time
                if time_done == datetime.max:
                    time_done = instr_sent_event.server_time
                # Use Action DONE for newer games
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
                time_cancelled = datetime.max
                if instruction.turn_completed in time_per_turn:
                    time_cancelled = time_per_turn
                if event_last_move and event_last_move.server_time > time_cancelled:
                    time_cancelled = event_last_move.server_time
                if time_cancelled == datetime.max:
                    time_cancelled = instr_sent_event.server_time
                instr_cancelled_event = Event(
                    game=new_game,
                    type=EventType.INSTRUCTION_CANCELLED,
                    server_time=time_cancelled,
                    turn_number=event_last_move.turn_number
                    if event_last_move
                    else instr_sent_event.turn_number,
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
                type=EventType.MOVE,
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
                    Event.type == EventType.MOVE,
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
            last_turn_state_i = bisect.bisect(
                game_turns, prop_update.time, key=lambda t: t.time
            )
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

        game_card_selections = sorted(card_selections, key=lambda s: s.game_time)
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
                    Event.type == EventType.MOVE,
                    Event.server_time <= selection.game_time,
                )
                .order_by(Event.server_time, Event.server_time.desc())
            )
            # It's very difficult and unnecessary to recover the card ID. Drop it for old games. In the future, we can recover this more easily using the new Event schema.
            is_selected = selection.type == "select"
            card_obj = card.Card(
                -1,
                selection.card.location,
                0,
                selection.card.shape,
                selection.card.color,
                selection.card.count,
                is_selected,
            )
            event = Event(
                game=new_game,
                type=EventType.CARD_SELECT,
                turn_number=selection.move.turn_number,
                origin=origin,
                role=selection.move.character_role,
                parent_event=move_event,
                data=JsonSerialize(card_obj),
                short_code=selection.type,
                location=selection.card.location,
                orientation=0,
                tick=-1,
            )

        game_card_sets = sorted(card_sets, key=lambda s: s.move.server_time)
        for card_set in game_card_sets:
            origin = (
                EventOrigin.LEADER
                if card_set.move.character_role == "Role.LEADER"
                else EventOrigin.FOLLOWER
            )
            move_event_query = (
                Event.select()
                .where(
                    Event.game == new_game,
                    Event.type == EventType.MOVE,
                    Event.server_time <= card_set.move.server_time,
                )
                .order_by(Event.server_time.desc())
            )
            if move_event_query.count() == 0:
                logger.error(
                    f"Could not find move event for card set {card_set.move.server_time} {card_set.move.turn_number}"
                )
                return
            move_event = move_event_query.get()
            data = {
                "cards": [card.Card.FromProp(prop) for prop in card_set.cards],
                "score": card_set.score,
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
        tick = 0
        last_event_time = datetime.min
        for event in (
            Event.select().where(Event.game == new_game).order_by(Event.server_time)
        ):
            if (
                event.server_time - last_event_time
            ).total_seconds() > 0.005 and last_event_time != datetime.min:
                tick += 1
            event.tick = tick
            event.save()
            last_event_time = event.server_time


def main(old_db_path, new_db_path):
    logging.basicConfig(level=logging.INFO)
    SwitchToDatabase(old_db_path)
    old_db = base.GetDatabase()

    old_assignments = []
    old_workers = []
    old_google_users = []
    old_remotes = []
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
    old_usernames = []
    old_leaderboards = []

    with old_db.connection_context():
        # Query all games.
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
            .order_by(Game.id)
        )

        for instruction in Instruction.select():
            if instruction.game_id not in old_instructions:
                old_instructions[instruction.game_id] = []
            old_instructions[instruction.game_id].append(instruction)

        # Query all moves.
        for move in (
            Move.select().join(Instruction, join_type=peewee.JOIN.LEFT_OUTER).select()
        ):
            if move.game_id not in old_moves:
                old_moves[move.game_id] = []
            if move.instruction:
                move.instruction = move.instruction
            old_moves[move.game_id].append(move)

        # Query all live feedback.
        for live_feedback in LiveFeedback.select().join(
            Instruction, join_type=peewee.JOIN.LEFT_OUTER
        ):
            if live_feedback.game_id not in old_live_feedback:
                old_live_feedback[live_feedback.game_id] = []
            live_feedback.instruction = live_feedback.instruction
            old_live_feedback[live_feedback.game_id].append(live_feedback)

        # Query all maps.
        for map_update in MapUpdate.select().join(Game).select():
            if map_update.game_id not in old_maps:
                old_maps[map_update.game_id] = []
            map_update.game = map_update.game
            old_maps[map_update.game_id].append(map_update)

        for prop_update in PropUpdate.select().join(Game).select():
            if prop_update.game_id not in old_props:
                old_props[prop_update.game_id] = []
            prop_update.game = prop_update.game
            old_props[prop_update.game_id].append(prop_update)

        # Query all card sets.
        for card_set in CardSets.select().join(Move).select():
            if card_set.game_id not in old_card_sets:
                old_card_sets[card_set.game_id] = []
            card_set.move = card_set.move
            old_card_sets[card_set.game_id].append(card_set)

        # Query all card selections.
        for card_selection in (
            CardSelections.select().join(Move).switch(CardSelections).join(Card)
        ):
            if card_selection.game_id not in old_card_selections:
                old_card_selections[card_selection.game_id] = []
            card_selection.move = card_selection.move
            card_selection.card = card_selection.card
            old_card_selections[card_selection.game_id].append(card_selection)

        for turn in Turn.select().join(Game).select():
            if turn.game_id not in old_turns:
                old_turns[turn.game_id] = []
            turn.game = turn.game
            old_turns[turn.game_id].append(turn)

        for init_state in InitialState.select().join(Game).select():
            if init_state.game_id not in old_initial_states:
                old_initial_states[init_state.game_id] = []
            init_state.game = init_state.game
            old_initial_states[init_state.game_id].append(init_state)

        old_assignments = Assignment.select()
        old_workers = Worker.select()
        old_worker_experience = WorkerExperience.select()
        old_google_users = GoogleUser.select()
        old_remotes = Remote.select()
        old_usernames = Username.select()
        old_leaderboards = Leaderboard.select()

    non_tutorial_games = [game for game in old_games if "tutorial" not in game.type]
    logger.info(f"Non tutorial games: {len(non_tutorial_games)}")

    # We've queried all tables. Print the size of each table.
    logger.info(f"Assignments: {len(old_assignments)}")
    logger.info(f"Workers: {len(old_workers)}")
    logger.info(f"Google Users: {len(old_google_users)}")
    logger.info(f"Remotes: {len(old_remotes)}")
    logger.info(f"Usernames: {len(old_usernames)}")
    logger.info(f"Leaderboards: {len(old_leaderboards)}")
    logger.info(f"Worker Experience: {len(old_worker_experience)}")
    logger.info(f"Games: {len(old_games)}")
    logger.info(f"Turns: {len(old_turns)}")
    logger.info(f"Instructions: {len(old_instructions)}")
    logger.info(f"Moves: {len(old_moves)}")
    logger.info(f"Live Feedback: {len(old_live_feedback)}")
    logger.info(f"Maps: {len(old_maps)}")
    logger.info(f"Card Sets: {len(old_card_sets)}")
    logger.info(f"Card Selections: {len(old_card_selections)}")
    logger.info(f"Initial States: {len(old_initial_states)}")

    # Log each game on its own line and confirm that we should continue the
    # merge. Print the number of games too.
    logger.info(f"Found {len(old_games)} games in {old_db}")
    if input("Continue? (y/n)") != "y":
        sys.exit(1)

    SwitchToDatabase(new_db_path)
    new_db = base.GetDatabase()
    base.CreateTablesIfNotExists(defaults.ListDefaultTables())

    # Migrate all the workers, assignments, google users and remotes.
    for worker_experience in old_worker_experience:
        worker_experience.save(force_insert=True)

    for worker in old_workers:
        worker.save(force_insert=True)

    for assignment in old_assignments:
        assignment.save(force_insert=True)

    for google_user in old_google_users:
        google_user.save(force_insert=True)

    for remote in old_remotes:
        remote.save(force_insert=True)

    for username in old_usernames:
        username.save(force_insert=True)

    for leaderboard in old_leaderboards:
        leaderboard.id = None
        leaderboard.save(force_insert=True)

    # Migrate all the games.
    for game in old_games:
        assert game.id in old_maps, f"Game {game.id} has no map!"
        if "tutorial" in game.type:
            logger.info(f"Skipping tutorial game {game.id} type: {game.type}...")
            continue
        print(f"Migrating game {game.id}/{len(old_games)}...")
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

    # Make sure we didn't leave any -1 ticks.
    for event in Event.select():
        if event.tick == -1:
            logger.error(f"Event {event.id} has tick -1!")

    logging.info("Done!")

    # Close the database.
    base.CloseDatabase()


if __name__ == "__main__":
    fire.Fire(main)
