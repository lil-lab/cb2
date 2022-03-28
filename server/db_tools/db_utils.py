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
    games = (Game.select()
            .join(Assignment, on=((Game.lead_assignment == Assignment.id) or (Game.follow_assignment == Assignment.id)), join_type=peewee.JOIN.LEFT_OUTER)
            .where(Game.valid == True,
                   Game.type == "game-mturk",
                   ((Game.lead_assignment != None) & (Game.lead_assignment.submit_to_url == "https://www.mturk.com") | 
                    ((Game.follow_assignment != None)& (Game.lead_assignment.submit_to_url == "https://www.mturk.com"))))
            .switch(Game))
    return games

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
    
    """
    # Join the game 
    is_valid = game.valid
    is_mturk = game.type == "game-mturk"
    has_leader_submit_url = game.lead_assignment is not None and game.lead_assignment.submit_to_url == "https://www.mturk.com"
    has_follower_submit_url = game.follow_assignment is not None and game.follow_assignment.submit_to_url == "https://www.mturk.com"
    if is_mturk:
        if game.lead_assignment is not None:
            print(f"Lead submit_to_url: {game.lead_assignment.submit_to_url}")
            print(f"has leader submit url: {has_leader_submit_url}")
        if game.follow_assignment is not None:
            print(f"Follow submit_to_url: {game.follow_assignment.submit_to_url}")
            print(f"has follower submit url: {has_follower_submit_url}")
    return is_valid and is_mturk and (has_leader_submit_url or has_follower_submit_url)