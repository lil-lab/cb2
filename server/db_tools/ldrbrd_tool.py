from schemas.mturk import Worker
from schemas.leaderboard import Username

import config.config as config
import leaderboard
import schemas.defaults
from schemas.leaderboard import Username, Leaderboard
from schemas import base
from db_tools import db_utils

import fire
import sys

COMMANDS = [
    "list",
    "delete",
    "recalculate",
    "list_names",
]

def PrintUsage():
    print("Usage:")
    print("  ldrbrd list")
    print("  ldrbrd delete --item=[0-9]")
    print("  ldrbrd delete --item=ALL")
    print("  ldrbrd recalculate")
    print("  ldrbrd list_names")

def main(command, item="", config_filepath="config/server-config.json"):
    cfg = config.ReadConfigOrDie(config_filepath)

    print(f"Reading database from {cfg.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(cfg.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    if command == "list":
        board = leaderboard.GetLeaderboard()
        for i, entry in enumerate(board):
            leader_name = leaderboard.LookupUsername(entry.leader)
            follower_name = leaderboard.LookupUsername(entry.follower)
            print(f"{i:3}: scr: {entry.score} ldr: {leader_name} flwr: {follower_name} time: {entry.time}")
    elif command == "delete":
        board = leaderboard.GetLeaderboard()
        if item == "ALL":
            print(f"You are about to delete all entries. Are you sure? (y/n)")
            if input() == "y":
                for entry in board:
                    entry.delete_instance()
            else:
                print("Aborting.")
                sys.exit(1)
        else:
            index = None
            try:
                index = int(item)
            except ValueError:
                pass
            if index is None or index >= 10 or index < 0:
                print("Invalid index.")
                sys.exit(1)
            entry = board[index]
            entry.delete_instance()
    elif command == "recalculate":
        print(f"This could take a while...")
        games = db_utils.ListResearchGames()
        for game in games:
            leaderboard.UpdateLeaderboard(game)
    elif command == "list_names":
        names = Username.select()
        for name in names:
            print(f"{name.username}: {name.worker.hashed_id}")
    else:
        PrintUsage()

if __name__ == "__main__":
    fire.Fire(main)