""" A set of database utils that are used across the codebase."""

import itertools
import logging
import peewee

from enum import Enum
from numpy import number

from server.schemas.game import Turn
from server.schemas.game import Game
from server.schemas.game import Instruction
from server.schemas.game import Move
from server.schemas.map import MapUpdate
from server.schemas.mturk import Worker
from server.schemas.mturk import Assignment

# This document makes reference to the following game classifications:
# - Mturk Games (ListMturkGames): Games where at least one player is an mturk worker.
# - Research Games (ListResearchGames): Games that have research-quality language
#   data. These games are chosen based on the criteria in IsGameResearchData.
# - Config games: Games filtered by the provided server configuration. This
#   allows us to filter out old games that used separate rules, and to pool mturk
#   games together by trial (server config).
# - Analysis Games (ListAnalysisGames): Games selected from the pool of research
#   games filtered by the provided configuration. (Research & Config).

logger = logging.getLogger(__name__)

def ListAnalysisGames(config):
    # Filter out games that are not research data, and also games that are not included in this configuration.
    # config has two fields that are relevant:
    #   analysis_game_id_ranges: A list of tuples of the form (start_id, end_id).
    #   analytics_since_game_id: The game ID to start the analysis from (discard all games before this).
    games = ListResearchGames()
    print(f"Number of research games: {len(games)}")
    if len(config.analysis_game_id_ranges) > 0:
        valid_ids = set(itertools.chain(*[range(x, y + 1) for x,y in config.analysis_game_id_ranges]))
        print(f"Filtered to game IDs: {valid_ids}")
        games = [game for game in games if game.id in valid_ids]
        print(f"Number of valid games after filter: {len(games)}")
    if config.analytics_since_game_id > 0:
        games = [game for game in games if game.id >= config.analytics_since_game_id]
    return games

def IsGameAnalysisData(config, game):
    if len(config.analysis_game_id_ranges) > 0:
        valid_ids = set(itertools.chain(*[range(x, y + 1) for x,y in config.analysis_game_id_ranges]))
        if game.id not in valid_ids:
            return False
    if config.analytics_since_game_id > 0:
        if game.id < config.analytics_since_game_id:
            return False
    return IsGameResearchData(game)

def IsConfigGame(config, game):
    if len(config.analysis_game_id_ranges) > 0:
        valid_ids = set(itertools.chain(*[range(x, y + 1) for x,y in config.analysis_game_id_ranges]))
        if game.id not in valid_ids:
            return False
    if config.analytics_since_game_id > 0:
        if game.id < config.analytics_since_game_id:
            return False
    return True

def ListResearchGames():
    games = ListMturkGames()
    ids = [game.id for game in games]
    logger.info(f"Max game ID before research filtering: {max(ids)}")
    return [game for game in games if IsGameResearchData(game)]

def ListMturkGames():
    games = (Game.select()
            .join(Assignment, on=((Game.lead_assignment == Assignment.id) or (Game.follow_assignment == Assignment.id)), join_type=peewee.JOIN.LEFT_OUTER)
            .where(Game.valid == True,
                   Game.type == "game-mturk",
                   ((Game.lead_assignment != None) & (Game.lead_assignment.submit_to_url == "https://www.mturk.com") | 
                    ((Game.follow_assignment != None)& (Game.lead_assignment.submit_to_url == "https://www.mturk.com"))))
            .switch(Game))
    return games

def is_mturk(game):
    return game.type == "game-mturk"

def is_mturk_sandbox(game):
    has_leader_submit_url = game.lead_assignment is not None and game.lead_assignment.submit_to_url == "https://www.mturk.com"
    has_follower_submit_url = game.follow_assignment is not None and game.follow_assignment.submit_to_url == "https://www.mturk.com"
    return (not has_leader_submit_url) and (not has_follower_submit_url)

def high_percent_instructions_incomplete(game_instructions):
    # Make sure there weren't too many instructions that never got completed.
    # Count the number of continuous incomplete instructions at the end of the game.
    unfinished_instructions = 0
    for instruction in game_instructions.order_by(Instruction.turn_issued.desc()):
        if instruction.turn_completed == -1:
            unfinished_instructions += 1
        else:
            break

    high_percent_instructions_incomplete = unfinished_instructions / game_instructions.count() >= 0.2 if game_instructions.count() > 0 else True
    return high_percent_instructions_incomplete

def high_percent_cancelled_instructions(game_instructions):
    # Compute the number of times the leader cancelled an active instruction
    cancelled_instructions = 0
    last_turn = -1
    total_active_instructions = 0

    for instruction in game_instructions.order_by(Instruction.turn_issued.desc()):
        cancelled = instruction.turn_cancelled != -1
        completed = instruction.turn_completed != -1

        if not cancelled and not completed:
            moves = Move.select().join(Instruction).where(Move.instruction == instruction,
                                                          Move.character_role == 'Role.FOLLOWER')
            if moves.count() > 0:
                total_active_instructions += 1
        elif cancelled:
            if instruction.turn_cancelled != last_turn:
                last_turn = instruction.turn_cancelled
                cancelled_instructions += 1
                total_active_instructions += 1
        else:
            total_active_instructions += 1

    high_percent_instructions_cancelled = cancelled_instructions / total_active_instructions >= 0.2 if total_active_instructions > 0 else True
    return high_percent_instructions_cancelled

def follower_got_lost(game_instructions):
    # Make sure the follower didn't get stuck on an instruction.
    finished_instructions = game_instructions.where(Instruction.turn_completed != -1)
    follower_got_lost = False
    for instruction in finished_instructions:
        moves = instruction.moves
        if moves.count() >= 25:
            follower_got_lost = True
            break

def short_game(game):
    # Make sure the game wasn't just given up on in the first 2 turns.
    number_of_turns = Turn.select().join(Game).where(Turn.game == game).count()
    return number_of_turns <= 2

class GameDiagnosis(Enum):
    NONE = 0
    DB_INVALID = 1
    NOT_MTURK = 2
    MTURK_SANDBOX = 3
    GAME_INCOMPLETE = 4  # No longer used. Incomplete games are still considered research data.
    SHORT_GAME = 5
    HIGH_PERCENT_INSTRUCTIONS_INCOMPLETE = 6
    HIGH_PERCENT_INSTRUCTIONS_CANCELLED = 7
    FOLLOWER_GOT_LOST = 8
    GOOD = 9

def DiagnoseGame(game):
    """Returns a string explaining why the game is invalid for research.

    Provided object must be joined with the Assignment table on both the lead_assignment and follow_assignment fields.
    It's easier to use ListResearchGames() above, which filters all games on this condition.

    A game is considered research data if it satisfies the following conditions:
    - The game's "valid" column is true (in the games table).
    - The game's "type" column is "game-mturk".
    - Either the game's "leader_assignment" or "follower_assignment" column is not null and has a submit URL of "https://www.mturk.com".
    - Low percentage of incomplete instructions (something like < 20%).
    - Any instruction with more than 25 moves invalidates the game (the follower clearly just got lost and never recovered). 
    """
    # Join the game 
    if not game.valid: # Bool field in the db to manually filter out bad games.
        return GameDiagnosis.DB_INVALID
    if not is_mturk(game): # Only mturk games are considered research data.
        return GameDiagnosis.NOT_MTURK
    if is_mturk_sandbox(game): # Only non-sandbox mturk games are considered research data.
        return GameDiagnosis.MTURK_SANDBOX
    if short_game(game): # Filter games that were just given up on.
        return GameDiagnosis.SHORT_GAME

    game_instructions = Instruction.select().join(Game).where(Instruction.game == game)
    if follower_got_lost(game_instructions):
        return GameDiagnosis.FOLLOWER_GOT_LOST
    if high_percent_cancelled_instructions(game_instructions): # > % of instructions cancelled.
        return GameDiagnosis.HIGH_PERCENT_INSTRUCTIONS_CANCELLED
    return GameDiagnosis.GOOD

def IsGameResearchData(game):
    """Returns True if the game is usable as research data.

    Provided object must be joined with the Assignment table on both the lead_assignment and follow_assignment fields.
    It's easier to use ListResearchGames() above, which filters all games on this condition.

    A game is considered research data if it satisfies the following conditions:
    - The game's "valid" column is true (in the games table).
    - The game's "type" column is "game-mturk".
    - Either the game's "leader_assignment" or "follower_assignment" column is not null and has a submit URL of "https://www.mturk.com".
    - Low percentage of incomplete instructions (something like < 20%).
    - Any instruction with more than 25 moves invalidates the game (the follower clearly just got lost and never recovered). 
    """
    return DiagnoseGame(game) == GameDiagnosis.GOOD
