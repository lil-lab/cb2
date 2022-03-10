""" Yikes, I forgot to log orientation_before in all my games so far!

    This script will go through all the games and calculate the orientation_before for all the turns by replaying action data.
"""

from map_tools import visualize
from playhouse.sqlite_ext import CSqliteExtDatabase
import peewee
import schemas.defaults
import schemas.game

from actor import Actor
from messages.rooms import Role

from hex import HecsCoord
from schemas.game import Turn
from schemas.game import Game
from schemas.game import Instruction
from schemas.game import Move
from schemas.map import MapUpdate
from schemas.mturk import Worker
from schemas import base
from config.config import Config

import fire
import pathlib
import matplotlib
import matplotlib.pyplot as plt
import sys
import time

import db_tools.db_utils as db_utils

# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    with open(config_path, 'r') as cfg_file:
        config = Config.from_json(cfg_file.read())
        return config

def main(config_path="config/latest-analysis.json", no_i_totally_know_what_im_doing_i_swear=False):
    config = ReadConfigOrDie(config_path)
    print(f"Reading database from {config.database_path()}")

    if not no_i_totally_know_what_im_doing_i_swear:
        print("This script is a total hack. It was made once to recover lost orientation values. If you're relying on it, then you're probably in a bad spot. To make this work, run via :\n\tpython3 -m db_tools.integrate_orientation --no_i_totally_know_what_im_doing_i_swear")
        sys.exit(1)

    print("You brave cookie. Overwriting all 'orientation_before' values in the move table. You have 15 seconds to regret this decision and ctrl-c out before it starts...")
    time.sleep(15)
    print("Starting...")

    # Setup the sqlite database used to record game actions.
    base.SetDatabase(config.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    games = db_utils.ListResearchGames()
    # For each game.
    for game in games:
        # Simulate the leader and follower
        leader_moves = Move.select().join(Game).where(Move.game == game, Move.character_role == "Role.LEADER").order_by(Move.id)
        follower_moves = Move.select().join(Game).where(Move.game == game, Move.character_role == "Role.FOLLOWER").order_by(Move.id)
        print(f"Processing game {game.id}")
        if leader_moves.count() != 0:
            leader_spawn = leader_moves.get().position_before
            leader =  Actor(0, 0, Role.LEADER, leader_spawn)
            for move in leader_moves:
                if leader.location() != move.position_before:
                    print(f"Leader desynced from {leader.location()} to {move.position_before}")
                move.orientation_before = leader.heading_degrees()
                leader.add_action(move.action)
                leader.step()
                move.save()
        if follower_moves.count() != 0:
            follower_spawn = follower_moves.get().position_before
            follower =  Actor(0, 0, Role.LEADER, follower_spawn)
            for move in follower_moves:
                if follower.location() != move.position_before:
                    print(f"Follower desynced from {follower.location()} to {move.position_before}")
                move.orientation_before = follower.heading_degrees()
                follower.add_action(move.action)
                follower.step()
                move.save()


if __name__ == "__main__":
    fire.Fire(main)
