""" Yikes, I forgot to log orientation_before in all my games so far!

    This script will go through all the games and calculate the orientation_before for all the turns by replaying action data.
"""

import sys
import time

import config.config as config
import db_tools.db_utils as db_utils
import fire
import schemas.defaults
import schemas.game
from actor import Actor
from messages.rooms import Role
from schemas import base
from schemas.game import Game, Move


def main(
    config_path="config/latest-analysis.json",
    no_i_totally_know_what_im_doing_i_swear=False,
):
    cfg = config.ReadConfigOrDie(config_path)
    print(f"Reading database from {cfg.database_path()}")

    # Warning to make sure the person running this reads this script first.
    if not no_i_totally_know_what_im_doing_i_swear:
        print(
            "This script is a total hack. It was made once to recover lost orientation values. If you're relying on it, at least read the code first. To make this work, run via :\n\tpython3 -m db_tools.integrate_orientation --no_i_totally_know_what_im_doing_i_swear"
        )
        sys.exit(1)

    # Warning to make sure the person running this actually reads this script before running it. Don't worry toooo much, I ran this once and it worked perfectly.
    print(
        "You brave cookie. Overwriting all 'orientation_before' values in the move table. You have 15 seconds to regret this decision and ctrl-c out before it starts..."
    )
    time.sleep(15)
    print("Starting...")

    # Setup the sqlite database used to record game actions.
    base.SetDatabase(cfg)
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    games = db_utils.ListResearchGames()
    # For each game.
    for game in games:
        # Simulate the leader and follower
        leader_moves = (
            Move.select()
            .join(Game)
            .where(Move.game == game, Move.character_role == "Role.LEADER")
            .order_by(Move.id)
        )
        follower_moves = (
            Move.select()
            .join(Game)
            .where(Move.game == game, Move.character_role == "Role.FOLLOWER")
            .order_by(Move.id)
        )
        print(f"Processing game {game.id}")
        if leader_moves.count() != 0:
            # In peewee, get() gives you the first item in a query. Queries are ordered by ID above so this should be the first move.
            leader_spawn = leader_moves.get().position_before
            leader = Actor(0, 0, Role.LEADER, leader_spawn)
            for move in leader_moves:
                # Should hopefully never happen, but just in case ;)
                if leader.location() != move.position_before:
                    print(
                        f"Leader desynced from {leader.location()} to {move.position_before}"
                    )
                move.orientation_before = leader.heading_degrees()
                leader.add_action(move.action)
                leader.step()
                move.save()
        if follower_moves.count() != 0:
            follower_spawn = follower_moves.get().position_before
            follower = Actor(0, 0, Role.LEADER, follower_spawn)
            for move in follower_moves:
                if follower.location() != move.position_before:
                    print(
                        f"Follower desynced from {follower.location()} to {move.position_before}"
                    )
                move.orientation_before = follower.heading_degrees()
                follower.add_action(move.action)
                follower.step()
                move.save()


if __name__ == "__main__":
    fire.Fire(main)
