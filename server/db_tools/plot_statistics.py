from map_tools import visualize
from playhouse.sqlite_ext import CSqliteExtDatabase
from collections import Counter
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
import hashlib
import itertools
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

# Calculated by https://cerealbar2.com/rules
def award(score):
    amt = 0.30
    awards = [0.15, 0.25, 0.25, 0.30, 0.30, 0.35, 0.35, 0.40, 0.40, 0.40, 0.40, 0.50, 0.50, 0.60]
    for i in range(score):
        if i < len(awards):
            amt += awards[i]
        if i >= len(awards):
            amt += awards[-1]
    return amt

def award(score):
    amt = 0.30
    awards = [0.15, 0.25, 0.25, 0.30, 0.30, 0.35, 0.35, 0.40, 0.40, 0.40, 0.40, 0.50, 0.50, 0.60]
    for i in range(score):
        if i < len(awards):
            amt += awards[i]
        if i >= len(awards):
            amt += awards[-1]
    return amt

def main(config_filepath="config/server-config.json", experienced_player_ids="~/repos/mturk_utils/examples/cerealbar2/workers/experienced.txt", output_dir="plots"):
    config = ReadConfigOrDie(config_filepath)

    print(f"Reading database from {config.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(config.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    experienced_players = []
    with pathlib.Path(experienced_player_ids).expanduser().open('r') as f:
        for line in f:
            line = line.strip()
            if line:
                experienced_players.append(line)
    experienced_hashes = [hashlib.md5(p.encode('utf-8')).hexdigest() for p in experienced_players]

    output_dir = pathlib.Path(output_dir).expanduser() / config.name
    # Create the directory if it doesn't exist.
    output_dir.mkdir(parents=False, exist_ok=True)

    games = db_utils.ListMturkGames()
    games = games.join(schemas.mturk.Worker, join_type=peewee.JOIN.LEFT_OUTER, on=((schemas.game.Game.leader == schemas.mturk.Worker.id) or (schemas.game.Game.follower == schemas.mturk.Worker.id))).order_by(Game.id)
    if len(config.analysis_game_id_ranges) > 0:
        valid_ids = set(itertools.chain(*[range(x, y) for x,y in config.analysis_game_id_ranges]))
        games = games.select().where(Game.id.in_(valid_ids))
        print(f"Filtering to games {valid_ids}")
        print(f"{games.count()} games remaining")
    scores = []
    durations = []
    player_scores = {}
    player_good_lead_games = {}
    player_good_follow_games = {}
    good_instructions = []
    good_game_cost = 0
    player_durations = {}
    players = set()
    total_cost = 0
    instructions = []
    vocab = Counter()
    good_vocab = Counter()
    bad_vocab = Counter()
    incomplete_instructions = []
    percent_incomplete_instructions = []
    moves_per_instruction = []
    good_games = []
    bad_games = []
    bad_instructions = []
    good_game_scores = []
    bad_game_scores = []
    experienced_only_scores = []
    # For each game.
    for game in games:
        # Calculate the cost of the game.
        cost = 2 * award(game.score)  # 2x for leader & follower.
        total_cost += cost
        game_instructions = Instruction.select().join(Game).where(Instruction.game == game)
        instructions.extend(game_instructions)

        # Add new words to the vocabulary set.
        for instruction in game_instructions:
            vocab.update(instruction.text.split())

        unfinished_instructions = game_instructions.where(Instruction.turn_completed == -1)
        incomplete_instructions.append(unfinished_instructions.count())

        finished_instructions = game_instructions.where(Instruction.turn_completed != -1)
        for instruction in finished_instructions:
            moves = Move.select().join(Instruction).where(Move.instruction == instruction)
            moves_per_instruction.append(moves.count())

        if game_instructions.count() != 0:
            percent_incomplete = unfinished_instructions.count() / game_instructions.count()
            percent_incomplete_instructions.append(percent_incomplete)

        game_good = db_utils.IsGameResearchData(game)

        if game_good:
            experienced_only_scores.append(game.score)
            good_game_cost += cost
            good_instructions.extend(game_instructions)
            good_games.append(game)
            good_game_scores.append(game.score)
            if game.leader:
                if game.leader not in player_good_lead_games:
                    player_good_lead_games[game.leader] = 0
                player_good_lead_games[game.leader]+=1
            if game.follower:
                if game.follower not in player_good_follow_games:
                    player_good_follow_games[game.follower] = 0
                player_good_follow_games[game.follower]+=1
            for instruction in game_instructions:
                good_vocab.update(instruction.text.split())
        else:
            bad_games.append(game)
            bad_game_scores.append(game.score)
            for instruction in game_instructions:
                bad_vocab.update(instruction.text.split())
            bad_instructions.extend(game_instructions)


        # Collect some statistics about each game.
        score = game.score
        duration_minutes = (game.end_time - game.start_time).total_seconds() / 60
        scores.append(score)
        durations.append(duration_minutes)
        if game.leader.hashed_id not in player_scores:
            player_scores[game.leader.hashed_id] = []
        player_scores[game.leader.hashed_id].append(score)
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

    # Plot good and bad scores in a histogram. Make the colors transparent so you can see both distributions.
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    ax.hist(good_game_scores, bins=20, alpha=0.5, label="Useful games", color="lime")
    ax.hist(bad_game_scores, bins=20, alpha=0.5, label="Filtered games", color="lightcoral")
    ax.set_xlabel("Score")
    ax.set_ylabel("Frequency")
    ax.legend()
    fig.savefig(output_dir / "good_and_bad_scores.png")

    # Plot ratio of score to duration via scatter plot.
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    ax.scatter(durations, scores)
    ax.set_xlabel("Duration (s)")
    ax.set_ylabel("Score")
    fig.savefig(output_dir / "score_vs_duration.png")

    # Players who's hash_id is in the set of experienced_hashes.
    experienced_players = [player for player in players if player.hashed_id in experienced_hashes]

    print("=== Summary Statistics ===")
    print(f"{len(players)} players.")
    print(f"{len(experienced_players)} experienced players (that participated).")
    print(f"{len(instructions)} total instructions.")
    print(f"{len(good_instructions)} useful instructions.")
    print(f"{len(bad_instructions)} useless instructions.")
    print(f"{games.count()} games.")
    print(f"{len(good_games)} useful games")
    print(f"{len(bad_games)} useless games")
    print(f"{total_cost:0.2f} total cost.")
    print(f"{total_cost / len(instructions):0.2f} average cost per instruction.")
    print(f"{total_cost / len(good_instructions):0.2f} average cost per useful instruction")
    print(f"{total_cost / games.count():0.2f} average cost per game.")
    print(f"{len(instructions) / games.count():0.2f} average instructions per game.")
    print(f"${good_game_cost:0.2f} Cost of useful games.")
    print(f"${total_cost:0.2f} Cost of all games.")
    print(f"{sum(scores) / len(scores):0.2f} Average score of all games.")
    print(f"{sum(good_game_scores) / len(good_game_scores):0.2f} Average score of useful games.")
    print(f"{sum(bad_game_scores) / len(bad_game_scores):0.2f} Average score of useless games.")
    print(f"{len(vocab)} Vocab size.")
    print(f"{len(good_vocab)} Vocab size of useful games.")
    print(f"{len(bad_vocab)} Vocab size of filtered games.")
    print(f"=== Vocab examples ===")
    for word in good_vocab:
        if word not in bad_vocab:
            print(f"{word} IS NOT in useless vocab.")
            break
    for word in bad_vocab:
        if word not in good_vocab:
            print(f"{word} IS NOT in useful vocab.")
            break
    
    
    # Plot ratio of score to duration via scatter plot, make each player a different color.
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    for player in players:
        player_label = "non-mturk"
        if player is not None:
            player_label = player.hashed_id[0:6]
        ax.scatter(player_durations[player], player_scores[player.hashed_id], label=player_label)
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

    print(f"=== Experienced players with bad performance ===")
    for hash in experienced_hashes:
        # Print "good" players with more than % of their games having a score of 0.
        if hash not in player_scores:
            continue
        scores = player_scores[hash]
        zero_scores = [score for score in scores if score == 0]
        if len(zero_scores) / len(scores) >= 0.5:
            print(f"{hash[0:6]} has {len(zero_scores)}/{len(scores)} games with a score of 0.")

    # Plot a histogram of the scores of good games.
    fig, ax = plt.subplots(1, 2, figsize=(10, 5))
    ax[0].hist(experienced_only_scores, bins=20)
    ax[0].set_xlabel("Experienced players scores")
    ax[0].set_ylabel("Frequency")
    fig.savefig(output_dir / "game_scores.png")

    print(f"Random sample of 10 useful games:")
    sample_size = min(10, len(good_games))
    for game in random.sample(good_games, sample_size):
        print(game.id)

    print(f"Random sample of 10 useless games:")
    sample_size = min(10, len(bad_games))
    for game in random.sample(bad_games, sample_size):
        print(game.id)

    # TODO(sharf): Plot a scatter plot between score and amount of positive and negative feedback used.
    # TODO(sharf): Plot how much positive & negative feedback was used.
    # TODO(sharf): Show plot of score vs duration with experienced and inexperienced being different colors.
    # TODO(sharf): Analyze experienced vs inexperienced vocabulary.

if __name__ == "__main__":
    fire.Fire(main)
