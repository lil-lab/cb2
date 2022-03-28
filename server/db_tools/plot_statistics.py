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
import random

import db_tools.db_utils as db_utils

# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    with open(config_path, 'r') as cfg_file:
        config = Config.from_json(cfg_file.read())
        return config

# Calculated by https://cerealbar2.com/rules though we have base pay of 0.30
# due to misconfig HIT. TODO(sharf): fix this.
def award(score):
    amt = 0.30
    awards = [0.15, 0.25, 0.25, 0.30, 0.30, 0.35, 0.35, 0.40, 0.40, 0.40, 0.40, 0.50, 0.50, 0.60]
    for i in range(score):
        if i < len(awards):
            amt += awards[i]
        if i >= len(awards):
            amt += awards[-1]
    return amt

def main(config_filepath="config/server-config.json", output_dir="plots"):
    config = ReadConfigOrDie(config_filepath)

    print(f"Reading database from {config.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(config.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    output_dir = pathlib.Path(output_dir).expanduser()
    # Create the directory if it doesn't exist.
    output_dir.mkdir(parents=False, exist_ok=True)

    games = db_utils.ListMturkGames()
    games = games.join(schemas.mturk.Worker, join_type=peewee.JOIN.LEFT_OUTER, on=((schemas.game.Game.leader == schemas.mturk.Worker.id) or (schemas.game.Game.follower == schemas.mturk.Worker.id))).order_by(Game.id)
    scores = []
    durations = []
    player_scores = {}
    player_good_lead_games = {}
    player_good_follow_games = {}
    good_instructions = 0
    good_game_cost = 0
    player_durations = {}
    players = set()
    total_cost = 0
    instructions = []
    incomplete_instructions = []
    percent_incomplete_instructions = []
    moves_per_instruction = []
    good_games = []
    bad_games = []
    # For each game.
    for game in games:
        # Calculate the cost of the game.
        cost = 2 * award(game.score)  # 2x for leader & follower.
        total_cost += cost
        game_instructions = Instruction.select().join(Game).where(Instruction.game == game)
        instructions.extend(game_instructions)

        game_good = True

        unfinished_instructions = game_instructions.where(Instruction.turn_completed == -1)
        incomplete_instructions.append(unfinished_instructions.count())

        finished_instructions = game_instructions.where(Instruction.turn_completed != -1)
        for instruction in finished_instructions:
            moves = Move.select().join(Instruction).where(Move.instruction == instruction)
            if moves.count() >= 25:
                game_good = False
            moves_per_instruction.append(moves.count())

        if game_instructions.count() != 0:
            percent_incomplete = unfinished_instructions.count() / game_instructions.count()
            percent_incomplete_instructions.append(percent_incomplete)
            if percent_incomplete >= 0.1:
                game_good = False
        
        if game_instructions.count() == 0:
            game_good = False
        
        if game_good:
            good_game_cost += cost
            good_instructions += game_instructions.count()
            good_games.append(game)
            if game.leader:
                if game.leader not in player_good_lead_games:
                    player_good_lead_games[game.leader] = 0
                player_good_lead_games[game.leader]+=1
            if game.follower:
                if game.follower not in player_good_follow_games:
                    player_good_follow_games[game.follower] = 0
                player_good_follow_games[game.follower]+=1
        else:
            bad_games.append(game)

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
    print(f"{len(instructions)} instructions.")
    print(f"{games.count()} games.")
    print(f"{total_cost:0.2f} total cost.")
    print(f"{total_cost / len(instructions):0.2f} average cost per instruction.")
    print(f"{total_cost / games.count():0.2f} average cost per game.")
    
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

    # Plot number of unfinished instructions per game in a histogram.
    fig, ax = plt.subplots(2, 2, figsize=(10, 10))
    ax[0][0].hist(incomplete_instructions, bins=20)
    ax[0][0].set_xlabel("Unfinished instructions per game.")
    ax[0][0].set_ylabel("Frequency")
    ax[0][1].hist(moves_per_instruction, bins=20)
    ax[0][1].set_xlabel("Moves per instruction.")
    ax[0][1].set_ylabel("Frequency")
    ax[1][0].hist(percent_incomplete_instructions, bins=20)
    ax[1][0].set_xlabel("Percent incomplete instructions per game.")
    ax[1][0].set_ylabel("Frequency")
    fig.savefig(output_dir / "instruction_quality.png")

    # Plot number of good games per leader.
    fig, ax = plt.subplots(1, 2, figsize=(10, 5))
    ax[0].hist(player_good_lead_games.values(), bins=20)
    ax[0].set_xlabel("Good lead games per player.")
    ax[0].set_ylabel("Frequency")
    ax[1].hist(player_good_follow_games.values(), bins=20)
    ax[1].set_xlabel("Good follow games per player.")
    ax[1].set_ylabel("Frequency")
    fig.savefig(output_dir / "player_game_quality.png")

    good_players = []
    for player in players:
        if player not in player_good_lead_games:
            continue
        if player not in player_good_follow_games:
            continue
        if player_good_lead_games[player] >= 1 and player_good_follow_games[player] >= 1:
            good_players.append(player)

    print(f"Number of good players: {len(good_players)}.")
    print(f"Number of players total: {len(players)}.")

    print(f"Number of good games: {len(good_games)}.")
    print(f"Number of good instructions: {good_instructions}.")

    print(f"Cost per good instruction: {total_cost / good_instructions:0.2f}.")
    print(f"Cost of only good games: {good_game_cost:0.2f}.")
    print(f"Cost per instruction (only good games): {good_game_cost / good_instructions:0.2f}.")

    print(f"Random sample of 10 good games:")
    for game in random.sample(good_games, 10):
        print(game.id)

    print(f"Random sample of 10 bad games:")
    for game in random.sample(bad_games, 10):
        print(game.id)

    print(f"Good players: ")
    for player in good_players:
        print(f"{player.hashed_id}")

    # TODO(sharf): Plot a scatter plot between score and amount of positive and negative feedback used.
    # TODO(sharf): Plot how much positive & negative feedback was used.

if __name__ == "__main__":
    fire.Fire(main)
