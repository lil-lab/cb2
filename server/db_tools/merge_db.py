# Okay so I kicked off a batch of games and everything was running well. Several
# hours in, I get a bunch of complaints that the server crashed. I look and it
# appears the disk is full. I quickly delete some /tmp files and move the DB to
# a different directory to create a new one and start over the games. I then restart the game with a fresh database.

# Note that all of this was unnecessary. The disk was full. Deleting tmp files
# was sufficient, I could have left the DB file alone. I moved the DB and
# started a new one out of precaution because I suspected the file itself might
# just be too big.  Obviously without any real reason to suspect this. I was
# just at a lunch with friends when the crash happened and had to leave to fix
# this at a cafe across the street with wifi. I did this because I was under a
# lot of time pressure and wasn't thinking 100% clearly.

# Well, now I gotta merge those files. Here's the script to do it.

# If you're reading this because a similar thing happened in the future, this
# script is probably out of date. Check the fields in schemas/* to make sure
# that all the fields are correctly handled.

import fire
import logging
import peewee
import sys

from pendulum import time

from schemas import base
from schemas.cards import CardSets, Card, CardSelections
from schemas.clients import Remote, ConnectionEvents
from schemas.game import Game, Turn, Instruction, Move, LiveFeedback
from schemas.map import MapUpdate
from schemas.mturk import Worker, Assignment, WorkerExperience
from schemas.leaderboard import Leaderboard, Username
from schemas.defaults import ListDefaultTables
from playhouse.sqlite_ext import CSqliteExtDatabase

logger = logging.getLogger(__name__)

class MainFromBranchWorkerIdTranslater(object):
    def __init__(self, branch_id_to_hash, main_worker_id_by_hash):
        self.branch_id_to_hash = branch_id_to_hash
        self.main_worker_id_by_hash = main_worker_id_by_hash

    def LookupMainId(self, branch_worker_id):
        # Not all games have an associated mturk worker.
        if branch_worker_id == None:
            return None
        if branch_worker_id in self.branch_id_to_hash:
            hash = self.branch_id_to_hash[branch_worker_id]
            if hash in self.main_worker_id_by_hash:
                return self.main_worker_id_by_hash[hash]
        raise ValueError(f"Could not find worker with branch mturk id {branch_worker_id}")

def SwitchToDatabase(db):
    base.SetDatabase(db)
    base.ConnectDatabase()

def main(db_main_path, db_branch_path):

    SwitchToDatabase(db_main_path)
    db_main = base.GetDatabase()

    logging.basicConfig(level=logging.INFO)

    main_worker_id_by_hash = {}
    worker_exp_id_by_hash = {}

    with db_main.connection_context():
        for worker in Worker.select():
            main_worker_id_by_hash[worker.hashed_id] = worker.id
            worker_exp_id_by_hash[worker.hashed_id] = worker.experience_id

    SwitchToDatabase(db_branch_path)
    db_branch = base.GetDatabase()

    branch_worker_id_to_hash = {}

    with db_branch.connection_context():
        for worker in Worker.select():
            branch_worker_id_to_hash[worker.id] = worker.hashed_id
        
    worker_id_translator = MainFromBranchWorkerIdTranslater(branch_worker_id_to_hash, main_worker_id_by_hash)

    games_from_db_b = None
    workers_from_db_b = None

    branch_workers = []
    branch_assignments = []
    branch_games = []
    branch_turns = []
    branch_instructions = []
    branch_moves = []
    branch_live_feedback = []
    branch_maps = []
    branch_card_sets = []
    branch_cards = []
    branch_card_selections = []

    # TODO sharf move all the ID translation here. It'll be safer as we're in branch context.
    with db_branch.connection_context():
        workers = Worker.select().order_by(Worker.id)
        for worker in workers:
            if worker.hashed_id not in main_worker_id_by_hash:
                logger.info(f"Worker {worker.id} not in {db_main}")
                sys.exit(1)
            if worker.hashed_id in main_worker_id_by_hash:
                worker.experience_id = worker_exp_id_by_hash[worker.hashed_id]
            branch_workers.append(worker)
        
        print(f"Found no new workers not in main branch already. That's good!")

        # Query all assignments and inner join with workers.
        for assignment in Assignment.select().join(Worker):
            if assignment.worker.hashed_id in main_worker_id_by_hash:
                assignment.worker_id = main_worker_id_by_hash[assignment.worker.hashed_id]
            branch_assignments.append(assignment)
        
        # Query all games.
        games = (Game.select()
                    .join(Worker, join_type=peewee.JOIN.LEFT_OUTER, on=((Game.leader == Worker.id) or (Game.follower == Worker.id)))
                    .join(Assignment, on=((Game.lead_assignment == Assignment.id) or (Game.follow_assignment == Assignment.id)), join_type=peewee.JOIN.LEFT_OUTER)
                    .order_by(Game.id))
        for game in games:
            if game.leader != None:
                leader_id = worker_id_translator.LookupMainId(game.leader_id)
            else:
                leader_id = None
            if game.follower != None: 
                follower_id = worker_id_translator.LookupMainId(game.follower_id)
            else:
                follower_id = None
            game.leader_id = leader_id
            game.follower_id = follower_id
            branch_games.append(game)
        
        # Query all moves.
        for move in Move.select():
            branch_moves.append(move)
        
        # Query all live feedback.
        for live_feedback in LiveFeedback.select():
            branch_live_feedback.append(live_feedback)
        
        # Query all maps.
        for map_update in MapUpdate.select():
            branch_maps.append(map_update)
        
        # Query all card sets.
        for card_set in CardSets.select():
            branch_card_sets.append(card_set)
        
        # Query all cards.
        for card in Card.select():
            branch_cards.append(card)
        
        # Query all card selections.
        for card_selection in CardSelections.select():
            branch_card_selections.append(card_selection)

        for instruction in Instruction.select():

            branch_instructions.append(instruction)
        
        for turn in Turn.select():
            branch_turns.append(turn)

    # We've queried all tables. Print the size of each table.
    logger.info(f"Workers: {len(branch_workers)}")
    logger.info(f"Assignments: {len(branch_assignments)}")
    logger.info(f"Games: {len(branch_games)}")
    logger.info(f"Turns: {len(branch_turns)}")
    logger.info(f"Instructions: {len(branch_instructions)}")
    logger.info(f"Moves: {len(branch_moves)}")
    logger.info(f"Live Feedback: {len(branch_live_feedback)}")
    logger.info(f"Maps: {len(branch_maps)}")
    logger.info(f"Card Sets: {len(branch_card_sets)}")
    logger.info(f"Cards: {len(branch_cards)}")
    logger.info(f"Card Selections: {len(branch_card_selections)}")

    # Log each game on its own line and confirm that we should continue the
    # merge. Print the number of games too.
    logger.info(f"Found {len(branch_games)} games in {db_branch}")
    for game in branch_games:
        logger.info(f"{game.id} {game.score} {game.leader_id} {game.follower_id}")
    if input("Continue? (y/n)") != "y":
        sys.exit(1)

    # Maps of old IDs to new IDs (branch db to main db) for updating foreign keys.
    # Yikes, what a mess...
    branch_to_main_game_id = {}
    branch_to_main_turn_id = {}
    branch_to_main_instruction_id = {}
    branch_to_main_move_id = {}
    branch_to_main_lf_id = {}
    branch_to_main_map_id = {}
    branch_to_main_card_set_id = {}
    branch_to_main_card_id = {}
    branch_to_main_card_selection_id = {}
    branch_to_main_assignment_id = {}
    
    SwitchToDatabase(db_main_path)
    db_main = base.GetDatabase()

    with db_main.connection_context():
        for assignment in branch_assignments:
            # Create a new assignment in the main DB with the same values.
            main_assignment = Assignment(assignment_id = assignment.assignment_id, worker=assignment.worker, hit_id=assignment.hit_id, submit_to_url=assignment.submit_to_url, time_used=assignment.time_used)
            main_assignment.save()
            branch_to_main_assignment_id[assignment.id] = main_assignment.id
        for game in branch_games:
            main_game = Game(
                    type=game.type, 
                    log_directory = game.log_directory,
                    world_seed = game.world_seed,
                    leader_id = game.leader_id,
                    follower_id = game.follower_id,
                    number_cards = game.number_cards,
                    score = game.score,
                    number_turns = game.number_turns,
                    start_time = game.start_time,
                    end_time = game.end_time,
                    completed = game.completed,
                    valid = game.valid,
                    who_is_agent = game.who_is_agent,
                    lead_assignment=branch_to_main_assignment_id[game.lead_assignment_id] if game.lead_assignment_id != None else None,
                    follow_assignment=branch_to_main_assignment_id[game.follow_assignment_id] if game.follow_assignment_id != None else None,
                    server_software_commit = game.server_software_commit)
            main_game.save()
            branch_to_main_game_id[game.id] = main_game.id
        for turn in branch_turns:
            main_turn = Turn(
                    game_id = branch_to_main_game_id[turn.game_id],
                    role = turn.role,
                    time = turn.time,
                    turn_number = turn.turn_number,
                    notes = turn.notes,
                    end_method = turn.end_method
            )
            main_turn.save()
            branch_to_main_turn_id[turn.id] = main_turn.id
        for instruction in branch_instructions:
            main_instruction = Instruction(
                game_id = branch_to_main_game_id[instruction.game_id],
                worker_id = worker_id_translator.LookupMainId(instruction.worker_id),
                uuid = instruction.uuid,
                text = instruction.text,
                time = instruction.time,
                instruction_number = instruction.instruction_number,
                turn_issued = instruction.turn_issued,
                turn_completed = instruction.turn_completed)
            main_instruction.save()
            branch_to_main_instruction_id[instruction.id] = main_instruction.id
        for move in branch_moves:
            main_move = Move(
                game_id = branch_to_main_game_id[move.game_id],
                instruction_id = branch_to_main_instruction_id[move.instruction_id] if move.instruction_id != None else None,
                character_role = move.character_role,
                worker_id = worker_id_translator.LookupMainId(move.worker_id),
                turn_number = move.turn_number,
                action = move.action,
                position_before = move.position_before,
                game_time = move.game_time,
                server_time = move.server_time,
                action_code = move.action_code,
                orientation_before = move.orientation_before
            )
            main_move.save()
            branch_to_main_move_id[move.id] = main_move.id
        for live_feedback in branch_live_feedback:
            main_live_feedback = LiveFeedback(
                game = branch_to_main_game_id[live_feedback.game_id],
                feedback_type = live_feedback.feedback_type,
                instruction_id = branch_to_main_instruction_id[live_feedback.instruction_id] if live_feedback.instruction_id != None else None,
                turn_number = live_feedback.turn_number,
                follower_position = live_feedback.follower_position,
                follower_orientation = live_feedback.follower_orientation,
                game_time = live_feedback.game_time,
                server_time = live_feedback.server_time
            )
            main_live_feedback.save()
            branch_to_main_lf_id[live_feedback.id] = main_live_feedback.id
        
        for map in branch_maps:
            main_map = MapUpdate(
                world_seed = map.world_seed,
                map_data = map.map_data,
                game_id = branch_to_main_game_id[map.game_id],
                map_update_number = map.map_update_number,
                time = map.time
            )
            main_map.save()
            branch_to_main_map_id[map.id] = main_map.id
        
        for card_set in branch_card_sets:
            main_card_set = CardSets(
                game_id = branch_to_main_game_id[card_set.game_id],
                move_id = branch_to_main_move_id[card_set.move_id],
                score = card_set.score,
            )
            main_card_set.save()
            branch_to_main_card_set_id[card_set.id] = main_card_set.id
        
        for card in branch_cards:
            main_card = Card(
                game_id = branch_to_main_game_id[card.game_id],
                count = card.count,
                color = card.color,
                shape = card.shape,
                location = card.location,
                set = branch_to_main_card_set_id[card.set_id] if card.set_id != None else None,
                turn_created = card.turn_created
            )
            main_card.save()
            branch_to_main_card_id[card.id] = main_card.id
        
        for card_selection in branch_card_selections:
            main_card_selection = CardSelections(
                game_id = branch_to_main_game_id[card_selection.game_id],
                move_id = branch_to_main_move_id[card_selection.move_id],
                card_id = branch_to_main_card_id[card_selection.card_id],
                type = card_selection.type,
                game_time = card_selection.game_time
            )
            main_card_selection.save()
            branch_to_main_card_selection_id[card_selection.id] = main_card_selection.id

    logging.info("Done!")

    # Close the database.
    db_main.close()
    db_branch.close()

if __name__  == "__main__":
    fire.Fire(main)