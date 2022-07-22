""" A set of database utils that are used across the codebase."""

import itertools
import logging
import peewee

from schemas.game import Turn
from schemas.game import Game
from schemas.game import Instruction
from schemas.game import Move
from schemas.map import MapUpdate
from schemas.mturk import Worker
from schemas.mturk import Assignment

# This document makes reference to the following game classifications:
# - Mturk Games (ListMturkGames): Games where at least one player is an mturk worker.
# - Research Games (ListResearchGames): Games that have research-quality language
#   data. These games are chosen based on the criteria in IsGameResearchData.
# - Analysis Games (ListAnalysisGames): Games selected from the pool of research
#   games filtered by the provided configuration. This allows us to filter out
#   old games that used different game rules, different pools of workers, or are
#   otherwise not relevant to the analysis.

logger = logging.getLogger(__name__)

def ListAnalysisGames(config):
    # Filter out games that are not research data, and also games that are not included in this configuration.
    # config has two fields that are relevant:
    #   analysis_game_id_ranges: A list of tuples of the form (start_id, end_id).
    #   analytics_since_game_id: The game ID to start the analysis from (discard all games before this).
    games = ListResearchGames()
    if len(config.analysis_game_id_ranges) > 0:
        valid_ids = set(itertools.chain(*[range(x, y) for x,y in config.analysis_game_id_ranges]))
        print(f"Filtered to game IDs: {valid_ids}")
        games = [game for game in games if game.id in valid_ids]
        print(f"Number of valid games after filter: {len(games)}")
    if config.analytics_since_game_id > 0:
        games = [game for game in games if game.id >= config.analytics_since_game_id]
    return games

def IsGameAnalysisData(config, game):
    if len(config.analysis_game_id_ranges) > 0:
        valid_ids = set(itertools.chain(*[range(x, y) for x,y in config.analysis_game_id_ranges]))
        if game.id not in valid_ids:
            return False
    if config.analytics_since_game_id > 0:
        if game.id < config.analytics_since_game_id:
            return False
    return IsGameResearchData(game)

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
    # Join the game 
    is_valid = game.valid
    is_mturk = game.type == "game-mturk"
    has_leader_submit_url = game.lead_assignment is not None and game.lead_assignment.submit_to_url == "https://www.mturk.com"
    has_follower_submit_url = game.follow_assignment is not None and game.follow_assignment.submit_to_url == "https://www.mturk.com"
    is_complete = game.completed

    # Filter out non-mturk games.
    if not is_mturk:
        return False

    game_instructions = Instruction.select().join(Game).where(Instruction.game == game)

    # Make sure there weren't too many instructions that never got completed.
    unfinished_instructions = game_instructions.where(Instruction.turn_completed == -1)
    high_percent_instructions_incomplete = unfinished_instructions.count() / game_instructions.count() >= 0.2 if game_instructions.count() > 0 else True

    # Make sure the follower didn't get stuck on an instruction.
    finished_instructions = game_instructions.where(Instruction.turn_completed != -1)
    follower_got_lost = False
    for instruction in finished_instructions:
        moves = instruction.moves
        if moves.count() >= 25:
            follower_got_lost = True
            break
    
    # Make sure the game wasn't just given up on in the first 2 turns.
    number_of_turns = Turn.select().join(Game).where(Turn.game == game).count()
    short_game = False
    if number_of_turns <= 2:
        return short_game

    return (is_valid  # Bool field in the game DB to manually filter out bad games.
            and is_mturk  # At least one worker was an mturk worker.
            and is_complete # The game is complete.
            and (has_leader_submit_url or has_follower_submit_url) # Non-sandboxed mturk.
            and not high_percent_instructions_incomplete # < 20% of instructions are incomplete.
            and not follower_got_lost  # No instruction with > 25 moves 
            and not short_game) # > 2 turns.