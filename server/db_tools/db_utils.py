""" A set of database utils that are used across the codebase."""

import peewee

from schemas.game import Turn
from schemas.game import Game
from schemas.game import Instruction
from schemas.game import Move
from schemas.map import MapUpdate
from schemas.mturk import Worker
from schemas.mturk import Assignment

def ListResearchGames():
    games = ListMturkGames()
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
        moves = Move.select().join(Instruction).where(Move.instruction == instruction)
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
            and (has_leader_submit_url or has_follower_submit_url) # Non-sandboxed mturk.
            and not high_percent_instructions_incomplete # < 20% of instructions are incomplete.
            and not follower_got_lost  # No instruction with > 25 moves 
            and not short_game) # > 2 turns.