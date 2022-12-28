# Adapted from merge_db.py.
# Migrates the old database schema to the new one.

import logging
import sys
from datetime import datetime

import fire
import orjson
import peewee

import server.card as card
import server.messages.turn_state as turn_msg
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
from server.schemas.map import MapUpdate
from server.schemas.mturk import Assignment, Worker
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
    moves,
    turn_states,
    instructions,
    live_feedback,
    maps,
    card_sets,
    cards,
    card_selections,
    prop_updates,
    initial_states,
):
    with new_db.connection_context():
        new_game = Game(
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
        new_game.save()

        map_update = (
            maps.select()
            .where(MapUpdate.game == old_game)
            .order_by(MapUpdate.server_time)
            .first()
        )
        map_event = Event(
            game=new_game.id,
            type=EventType.MAP_UPDATE,
            turn_number=0,
            origin=EventOrigin.SERVER,
            data=map_update.map_data.to_json(),
        )
        map_event.save(force_insert=True)

        prop_update = (
            prop_updates.select()
            .where(PropUpdate.game == old_game)
            .order_by(PropUpdate.server_time)
            .first()
        )
        prop_event = Event(
            game=new_game.id,
            type=EventType.PROP_UPDATE,
            turn_number=0,
            origin=EventOrigin.SERVER,
            data=prop_update.to_json(),
        )
        prop_event.save(force_insert=True)

        game_turns = (
            turn_states.select().where(Turn.game == old_game).order_by(Turn.time)
        )
        final_turn = game_turns.last()
        last_turn = None
        for i, turn_state in enumerate(game_turns):
            event_type = EventType.TURN_STATE
            if not last_turn or (last_turn.role != turn_state.role):
                event_type = EventType.START_OF_TURN
            moves_remaining = 10 if turn_state.role == Role.LEADER else 5
            last_score = (
                card_sets.select()
                .where(
                    CardSets.game == old_game,
                    CardSets.move.server_time <= turn_state.time,
                )
                .order_by(CardSets.move.server_time.desc())
                .first()
            )
            turn_state_obj = turn_msg.TurnState(
                turn_state.role,
                moves_remaining,
                final_turn.turn_number - turn_state.turn_number,
                datetime.max,
                old_game.start_time,
                last_score.score,
                last_score.score,
                i == len(turns) - 1,
                turn_state.turn_number,
            )
            event = Event(
                game=new_game,
                type=event_type,
                turn_number=turn_state.turn_number,
                server_time=turn_state.time,
                origin=EventOrigin.SERVER,
                data=JsonSerialize(turn_state_obj),
                short_code="",
                role=turn_state.role,
            )
            last_turn = turn_state

        initial_state = (
            initial_states.select()
            .where(InitialState.game == old_game)
            .order_by(InitialState.server_time)
            .first()
        )
        initial_state_obj = schema_util.InitialState(
            leader_id=initial_state.leader_id,
            follower_id=initial_state.follower_id,
            leader_position=initial_state.leader_position,
            leader_rotation_degrees=initial_state.leader_rotation_degrees,
            follower_position=initial_state.follower_position,
            follower_rotation_degrees=initial_state.follower_rotation_degrees,
        )
        initial_state_event = Event(
            game=new_game.id,
            type=EventType.INITIAL_STATE,
            turn_number=0,
            origin=EventOrigin.SERVER,
            data=JsonSerialize(initial_state),
        )
        initial_state_event.save(force_insert=True)

        game_instructions = instructions.where(Instruction.game == old_game)
        event_per_i_uuid = {}
        for instruction in game_instructions:
            instr_sent_event = Event(
                game=new_game.id,
                type=EventType.INSTRUCTION_SENT,
                server_time=instruction.time,
                turn_number=instruction.turn_issued,
                origin=EventOrigin.LEADER,
                role="Role.LEADER",
                data=ObjectiveMessage(
                    Role.LEADER, instruction.text, instruction.uuid, False, False
                ).to_json(),
                short_code=instruction.uuid,
            )
            instr_sent_event.save(force_insert=True)
            event_per_i_uuid[instruction.uuid] = instr_sent_event
            event_first_move = (
                moves.where(Move.game == old_game, Move.instruction == instruction)
                .order_by(Move.server_time)
                .first()
            )
            event_last_move = (
                moves.where(Move.game == old_game, Move.instruction == instruction)
                .order_by(Move.server_time)
                .last()
            )
            instr_activated_event = Event(
                game=new_game.id,
                type=EventType.INSTRUCTION_ACTIVATED,
                server_time=event_first_move.server_time,
                turn_number=event_first_move.turn_number,
                origin=EventOrigin.SERVER,
                role="Role.FOLLOWER",
                parent_event=instr_sent_event.id,
                short_code=instruction.uuid,
            )
            instr_activated_event.save(force_insert=True)
            if instruction.turn_completed != -1:
                instr_done_event = Event(
                    game=new_game.id,
                    type=EventType.INSTRUCTION_DONE,
                    server_time=event_last_move.server_time,
                    turn_number=event_last_move.turn_number,
                    origin=EventOrigin.FOLLOWER,
                    role="Role.FOLLOWER",
                    short_code=instruction.uuid,
                    parent_event=instr_sent_event.id,
                )
                instr_done_event.save(force_insert=True)
            elif instruction.turn_cancelled != -1:
                instr_cancelled_event = Event(
                    game=new_game.id,
                    type=EventType.INSTRUCTION_CANCELLED,
                    server_time=event_last_move.server_time,
                    turn_number=event_last_move.turn_number,
                    origin=EventOrigin.LEADER,
                    role="Role.LEADER",
                    short_code=instruction.uuid,
                    parent_event=instr_sent_event.id,
                )
                instr_cancelled_event.save(force_insert=True)

        game_moves = moves.where(Move.game == old_game)
        for move in game_moves:
            origin = (
                EventOrigin.LEADER
                if move.character_role == "Role.LEADER"
                else EventOrigin.FOLLOWER
            )
            # Generate an event from the move.
            move_event = Event(
                game=new_game.id,
                type=EventType.MOVE,
                server_time=move.server_time,
                origin=origin,
                role=move.character_role,
                # parent_event
                parent_event=event_per_i_uuid[move.instruction.uuid].id
                if move.instruction is not None
                else None,
                short_code=move.action_code,
                data=move.action,
                location=move.position_before,
                orientation=move.orientation_before,
            )
            move_event.save(force_insert=True)

        game_feedback = feedback.where(LiveFeedback.game == old_game)
        for feedback in game_feedback:
            last_move = (
                Event.select()
                .where(
                    Event.game == new_game.id,
                    Event.origin == EventOrigin.FOLLOWER,
                    Event.type == EventType.MOVE,
                    Event.server_time < feedback.server_time,
                )
                .order_by(Event.server_time.desc())
                .first()
            )
            feedback_data = live_feedback.LiveFeedback(
                live_feedback.FeedbackType(feedback.feedback_type)
            )
            short_code = ""
            if feedback_data.signal == live_feedback.FeedbackType.POSITIVE:
                short_code = "Positive"
            elif feedback_data.signal == live_feedback.FeedbackType.NEGATIVE:
                short_code = "Negative"
            elif feedback_data.signal == live_feedback.FeedbackType.NONE:
                short_code = "None"
            event = Event(
                server_time=feedback.server_time,
                game=new_game.id,
                type=EventType.LIVE_FEEDBACK,
                turn_number=feedback.turn_number,
                origin=EventOrigin.LEADER,
                role="Role.LEADER",
                parent_event=last_move,
                data=feedback_data,
                short_code=short_code,
                location=feedback.follower_position,
                orientation=feedback.follower_orientation,
            )
            event.save(force_insert=True)

        game_prop_updates = prop_updates.where(PropUpdate.game == old_game).order_by(
            PropUpdate.time
        )
        for i, prop_update in enumerate(game_prop_updates):
            # First prop update is captured above.
            if i == 0:
                continue
            prop_data = prop_update.prop_data
            last_prop_data = game_prop_updates[i - 1].prop_data
            new_prop_ids = set([p.id for p in prop_data.props]) - set(
                [p.id for p in last_prop_data.props]
            )
            last_turn_state = (
                game_turns.where(Turn.game == old_game, Turn.time <= prop_update.time)
                .order_by(Turn.time.desc())
                .first()
            )
            for prop in prop_data.props:
                if prop.id not in new_prop_ids:
                    continue
                card = card.Card.FromProp(prop)
                short_code = " ".join([card.count, card.color, card.shape])
                prop_event = Event(
                    game=new_game,
                    type=EventType.CARD_SPAWN,
                    server_time=prop_update.time,
                    turn_number=last_turn_state.turn_number,
                    origin=EventOrigin.SERVER,
                    data=JsonSerialize(card),
                    short_code=short_code,
                    location=card.location,
                    orientation=card.rotation_degrees,
                )

        game_card_selections = (
            card_selections.select()
            .where(CardSelections.game == old_game)
            .order_by(CardSelections.game_time)
        )
        for selection in game_card_selections:
            origin = (
                EventOrigin.LEADER
                if selection.move.character_role == "Role.LEADER"
                else EventOrigin.FOLLOWER
            )
            # Even though it's called game_time, game_time is populated with
            # utcnow (as if it's server_time), making the name a misnomer.
            move_event = (
                Event.select()
                .where(
                    Event.game == new_game,
                    Event.Type == EventType.MOVE,
                    Event.server_time <= selection.game_time,
                )
                .order_by(Event.server_time)
                .last()
            )
            # It's very difficult and unnecessary to recover the card ID. Drop it for old games. In the future, we can recover this more easily using the new Event schema.
            is_selected = selection.type == "select"
            card = card.Card(
                -1,
                selection.card.location,
                selection.card.rotation_degrees,
                selection.card.shape,
                selection.card.color,
                selection.card.count,
                is_selected,
            )
            event = Event(
                game=new_game,
                type=EventType.CARD_SELECT,
                turn_number=selection.move.turn_number,
                origin=selection.move.origin,
                role=selection.move.character_role,
                parent_event=move_event,
                data=JsonSerialize(card),
                short_code=selection.type,
                location=selection.card.location,
                orientation=0,
            )

        game_card_sets = (
            card_sets.select().where(CardSets.game == old_game).order_by(CardSets.time)
        )
        for card_set in game_card_sets:
            origin = (
                EventOrigin.LEADER
                if card_set.move.character_role == "Role.LEADER"
                else EventOrigin.FOLLOWER
            )
            move_event = (
                Event.select()
                .where(
                    Event.game == new_game,
                    Event.type == EventType.MOVE,
                    Event.server_time <= card_set.move.server_time,
                )
                .order_by(Event.server_time)
                .last()
            )
            data = {
                "cards": [card.Card.FromProp(prop) for prop in card_set.cards],
                "score": card_set.score,
            }
            card_set_event = Event(
                game=new_game,
                type=EventType.CARD_SET,
                server_time=card_set.time,
                turn_number=card_set.move.turn_number,
                origin=origin,
                data=JsonSerialize(data),
                parent_event=move_event,
                short_code=card_set.score,
            )
            card_set_event.save(force_insert=True)

        # Now iterate over all the created events in order of server_time. Assign a monotonically increasing tick. If two events occurred within 5ms of each other, assign them the same tick.
        tick = 0
        last_event_time = datetime.datetime.min
        for event in (
            Event.select().where(Event.game == new_game).order_by(Event.server_time)
        ):
            if (
                event.server_time - last_event_time
            ).total_seconds() > 0.005 and last_event_time != datetime.datetime.min:
                tick += 1
            event.tick = tick
            event.save()
            last_event_time = event.server_time


def main(old_db_path, new_db_path):
    logging.basicConfig(level=logging.INFO)
    SwitchToDatabase(old_db_path)
    old_db = base.GetDatabase()

    old_assignments = []
    old_games = []
    old_turns = []
    old_instructions = []
    old_moves = []
    old_live_feedback = []
    old_maps = []
    old_card_sets = []
    old_cards = []
    old_card_selections = []
    old_initial_states = []

    # TODO sharf move all the ID translation here. It'll be safer as we're in branch context.
    with old_db.connection_context():
        # Query all games.
        games = (
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

        old_instructions = Instruction.select()

        # Query all moves.
        old_moves = Move.select().join(Instruction)

        # Query all live feedback.
        old_live_feedback = LiveFeedback.select().join(Instruction)

        # Query all maps.
        old_maps = MapUpdate.select().join(Game)

        # Query all card sets.
        old_card_sets = CardSets.select().join(Move)

        # Query all cards.
        old_cards = Card.select().join(CardSets)

        # Query all card selections.
        old_card_selections = (
            CardSelections.select().join(Move).switch(CardSelections).join(Card)
        )

        old_turns = Turn.select().Join(Game)

        old_initial_states = InitialState.select().join(Game)

    # We've queried all tables. Print the size of each table.
    logger.info(f"Assignments: {len(old_assignments)}")
    logger.info(f"Games: {len(old_games)}")
    logger.info(f"Turns: {len(old_turns)}")
    logger.info(f"Instructions: {len(old_instructions)}")
    logger.info(f"Moves: {len(old_moves)}")
    logger.info(f"Live Feedback: {len(old_live_feedback)}")
    logger.info(f"Maps: {len(old_maps)}")
    logger.info(f"Card Sets: {len(old_card_sets)}")
    logger.info(f"Cards: {len(old_cards)}")
    logger.info(f"Card Selections: {len(old_card_selections)}")

    # Log each game on its own line and confirm that we should continue the
    # merge. Print the number of games too.
    logger.info(f"Found {len(old_games)} games in {old_db}")
    for game in old_games:
        logger.info(f"{game.id} {game.score} {game.leader_id} {game.follower_id}")
    if input("Continue? (y/n)") != "y":
        sys.exit(1)

    SwitchToDatabase(new_db_path)
    new_db = base.GetDatabase()

    for game in old_games:
        print(f"Migrating game {game.id}/{len(old_games)}...")
        migrate_to_new_game(
            new_db,
            game,
            old_moves,
            old_turns,
            old_instructions,
            old_live_feedback,
            old_maps,
            old_card_sets,
            old_cards,
            old_card_selections,
            old_initial_states,
        )

    logging.info("Done!")

    # Close the database.
    db_main.close()
    db_branch.close()


if __name__ == "__main__":
    fire.Fire(main)
