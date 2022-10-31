""" This tool analyzes the games to determine which players are considered "experienced". """

import itertools
import pathlib
import random

import db_tools.db_utils as db_utils
import fire
import matplotlib.pyplot as plt
import peewee
import schemas.defaults
import schemas.game
from config.config import Config
from schemas import base
from schemas.game import Game, Instruction, Move


# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    with open(config_path, "r") as cfg_file:
        config = Config.from_json(cfg_file.read())
        return config


# Calculated by https://cerealbar2.com/rules though we have base pay of 0.30
# due to misconfig HIT. TODO(sharf): fix this.
def award(score):
    amt = 0.30
    awards = [
        0.15,
        0.25,
        0.25,
        0.30,
        0.30,
        0.35,
        0.35,
        0.40,
        0.40,
        0.40,
        0.40,
        0.50,
        0.50,
        0.60,
    ]
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
    base.SetDatabase(config)
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    output_dir = pathlib.Path(output_dir).expanduser() / config.name
    # Create the directory if it doesn't exist.
    output_dir.mkdir(parents=False, exist_ok=True)

    games = db_utils.ListMturkGames()
    games = games.join(
        schemas.mturk.Worker,
        join_type=peewee.JOIN.LEFT_OUTER,
        on=(
            (schemas.game.Game.leader == schemas.mturk.Worker.id)
            or (schemas.game.Game.follower == schemas.mturk.Worker.id)
        ),
    ).order_by(Game.id)
    if len(config.analysis_game_id_ranges) > 0:
        valid_ids = set(itertools.chain(*config.analysis_game_id_ranges))
        games = games.select().where(Game.id.in_(valid_ids))
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
    good_game_scores = []
    # For each game.
    for game in games:
        # Calculate the cost of the game.
        cost = 2 * award(game.score)  # 2x for leader & follower.
        total_cost += cost
        game_instructions = (
            Instruction.select().join(Game).where(Instruction.game == game)
        )
        instructions.extend(game_instructions)

        game_good = True

        unfinished_instructions = game_instructions.where(
            Instruction.turn_completed == -1
        )
        incomplete_instructions.append(unfinished_instructions.count())

        finished_instructions = game_instructions.where(
            Instruction.turn_completed != -1
        )
        for instruction in finished_instructions:
            moves = (
                Move.select().join(Instruction).where(Move.instruction == instruction)
            )
            if moves.count() >= 25:
                game_good = False
            moves_per_instruction.append(moves.count())

        if game_instructions.count() != 0:
            percent_incomplete = (
                unfinished_instructions.count() / game_instructions.count()
            )
            percent_incomplete_instructions.append(percent_incomplete)
            if percent_incomplete >= 0.1:
                game_good = False

        if game_instructions.count() == 0:
            game_good = False

        if game_good:
            good_game_cost += cost
            good_instructions += game_instructions.count()
            good_games.append(game)
            good_game_scores.append(game.score)
            if game.leader:
                if game.leader not in player_good_lead_games:
                    player_good_lead_games[game.leader] = 0
                player_good_lead_games[game.leader] += 1
            if game.follower:
                if game.follower not in player_good_follow_games:
                    player_good_follow_games[game.follower] = 0
                player_good_follow_games[game.follower] += 1
        else:
            bad_games.append(game)

        # Collect some statistics about each game.
        score = game.score
        duration_minutes = (game.end_time - game.start_time).total_seconds() / 60
        game.number_turns
        scores.append(score)
        durations.append(duration_minutes)
        if game.leader not in player_scores:
            player_scores[game.leader] = []
        player_scores[game.leader].append(score)
        if game.leader not in player_durations:
            player_durations[game.leader] = []
        players.add(game.leader)
        player_durations[game.leader].append(duration_minutes)

    print(f"{len(players)} leaders.")
    print(f"{len(instructions)} instructions.")
    print(f"{games.count()} games.")
    print(f"{total_cost:0.2f} total cost.")
    print(f"{total_cost / len(instructions):0.2f} average cost per instruction.")
    print(f"{total_cost / games.count():0.2f} average cost per game.")

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
        if (
            player_good_lead_games[player] >= 1
            and player_good_follow_games[player] >= 1
        ):
            good_players.append(player)

    print(f"Experienced players with zero-games: ")
    new_good_players = []
    for player in good_players:
        # Print "good" players with more than 30% of their games having a score of 0.
        if player not in player_scores:
            print(f"Missing scores for player {player}.")
        scores = player_scores[player]
        zero_scores = [score for score in scores if score == 0]
        if len(zero_scores) / len(scores) >= 0.5:
            print(
                f"{player.hashed_id} has {len(zero_scores)}/{len(scores)} games with a score of 0."
            )
        else:
            new_good_players.append(player)
    good_players = new_good_players

    experienced_only_scores = []
    for game in games:
        if game.leader not in good_players:
            continue
        if game.follower not in good_players:
            continue
        experienced_only_scores.append(game.score)

    # Plot a histogram of the scores of good games.
    fig, ax = plt.subplots(1, 2, figsize=(10, 5))
    ax[0].hist(experienced_only_scores, bins=20)
    ax[0].set_xlabel("Experienced players scores")
    ax[0].set_ylabel("Frequency")
    fig.savefig(output_dir / "game_scores.png")

    # Plot number of good games per leader.
    fig, ax = plt.subplots(1, 2, figsize=(10, 5))
    ax[0].hist(player_good_lead_games.values(), bins=20)
    ax[0].set_xlabel("Good lead games per player.")
    ax[0].set_ylabel("Frequency")
    ax[1].hist(player_good_follow_games.values(), bins=20)
    ax[1].set_xlabel("Good follow games per player.")
    ax[1].set_ylabel("Frequency")
    fig.savefig(output_dir / "player_game_quality.png")

    print(f"Number of good players: {len(good_players)}.")
    print(f"Number of players total: {len(players)}.")

    print(f"Number of good games: {len(good_games)}.")
    print(f"Number of good instructions: {good_instructions}.")

    print(f"Cost per good instruction: {total_cost / good_instructions:0.2f}.")
    print(f"Cost of only good games: {good_game_cost:0.2f}.")
    print(
        f"Cost per instruction (only good games): {good_game_cost / good_instructions:0.2f}."
    )

    print(f"Random sample of 10 good games:")
    sample_size = min(10, len(good_games))
    for game in random.sample(good_games, sample_size):
        print(game.id)

    print(f"Random sample of 10 bad games:")
    sample_size = min(10, len(bad_games))
    for game in random.sample(bad_games, sample_size):
        print(game.id)

    print(f"Good players: ")
    for player in good_players:
        print(f"{player.hashed_id}")


if __name__ == "__main__":
    fire.Fire(main)
