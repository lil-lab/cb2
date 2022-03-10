# Creates a set of graphics where an instruction is displayed on the left, and
# the follower's pathway is displayed on the right.
from map_tools import visualize
from playhouse.sqlite_ext import CSqliteExtDatabase
import peewee
import schemas.defaults
import schemas.game

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

import db_tools.db_utils as db_utils

# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    with open(config_path, 'r') as cfg_file:
        config = Config.from_json(cfg_file.read())
        return config

def main(config_path="config/server-config.json", output_dir="plots"):
    config = ReadConfigOrDie(config_path)

    print(f"Reading database from {config.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(config.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    output_dir = pathlib.Path(output_dir).expanduser()
    # Create the directory if it doesn't exist.
    output_dir.mkdir(parents=False, exist_ok=True)

    games = db_utils.ListResearchGames()
    games = games.join(schemas.mturk.Worker, join_type=peewee.JOIN.LEFT_OUTER, on=((schemas.game.Game.leader == schemas.mturk.Worker.id) or (schemas.game.Game.follower == schemas.mturk.Worker.id))).order_by(Game.id)
    scores = []
    durations = []
    player_scores = {}
    player_durations = {}
    players = set()
    # For each game.
    for game in games:
        # Collect some statistics about each game.
        score = game.score
        duration_minutes = (game.end_time - game.start_time).total_seconds() / 60
        number_turns = game.number_turns
        scores.append(score)
        durations.append(duration_minutes)
        if game.leader not in player_scores:
            player_scores[game.leader] = []
        player_scores[game.leader].append(score)
        if game.leader not in player_durations:
            player_durations[game.leader] = []
        players.add(game.leader)
        player_durations[game.leader].append(duration_minutes)

    # Plot scores and durations via a histogram.
    fig, ax = plt.subplots(1, 2, figsize=(10, 5))
    ax[0].hist(scores, bins=20)
    ax[0].set_xlabel("Score")
    ax[0].set_ylabel("Frequency")
    ax[1].hist(durations, bins=20)
    ax[1].set_xlabel("Duration (m)")
    ax[1].set_ylabel("Frequency")
    fig.savefig(output_dir / "scores_and_durations.png")

    # Plot ratio of score to duration via scatter plot.
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    ax.scatter(durations, scores)
    ax.set_xlabel("Duration (s)")
    ax.set_ylabel("Score")
    fig.savefig(output_dir / "score_vs_duration.png")

    print(f"{len(players)} leaders.")
    
    # Plot ratio of score to duration via scatter plot, make each player a different color.
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    for player in players:
        player_label = "non-mturk"
        if player is not None:
            player_label = player.hashed_id[0:6]
        ax.scatter(player_durations[player], player_scores[player], label=player_label)
    ax.set_xlabel("Duration (s)")
    ax.set_ylabel("Score")
    ax.legend()
    fig.savefig(output_dir / "score_vs_duration_by_leader.png")

if __name__ == "__main__":
    fire.Fire(main)
