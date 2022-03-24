from schemas.mturk import Worker
from schemas.leaderboard import Username

import config.config as config
import leaderboard
import schemas.defaults
from schemas.leaderboard import Username, Leaderboard
from schemas import base
from db_tools import db_utils

import fire
import humanhash
import hashlib
import pathlib
import sys

COMMANDS = [
    "list",
    "delete",
    "regen_leaderboard",
    "list_names",
    "id_lookup",
    "hash_lookup",
    "reverse_hash",
    "reverse_name",
    "help",
    "calc_hash",
]

def PrintUsage():
    print("Usage:")
    print("  ldrbrd list")
    print("  ldrbrd delete --item=[0-9]")
    print("  ldrbrd delete --item=ALL")
    print("  ldrbrd regen_leaderboard")
    print("  ldrbrd list_names")
    print("  ldrbrd calc_hash --id=<worker_id>")
    print("  ldrbrd id_lookup --id=<worker_id>")
    print("  ldrbrd hash_lookup --hash=<md5sum>")
    print("  ldrbrd reverse_hash --hash=<md5sum> --workers_file=<filepath>")
    print("  ldrbrd reverse_name --name=<username> --workers_file=<filepath>")
    print("  ldrbrd help")

def ReverseHash(worker_hash, workers_file):
  path = pathlib.PosixPath(workers_file).expanduser()
  with path.open() as wlist:
    for worker in wlist:
      worker = worker.strip()
      md5sum = hashlib.md5(worker.encode('utf-8')).hexdigest()
      if worker_hash is not None:
        if md5sum == worker_hash:
          return worker

def ReverseUsername(worker_name, workers_file): 
  path = pathlib.PosixPath(workers_file).expanduser()
  with path.open() as wlist:
    for worker in wlist:
      worker = worker.strip()
      md5sum = hashlib.md5(worker.encode('utf-8')).hexdigest()
      name = humanhash.humanize(md5sum, words=2)
      if worker_name is not None:
        if name == worker_name:
          return worker

def main(command, id="", hash="", name="", workers_file = "", item="", config_filepath="config/server-config.json"):
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
    elif command == "regen_leaderboard":
        print(f"This could take a while...")
        games = db_utils.ListResearchGames()
        for game in games:
            leaderboard.UpdateLeaderboard(game)
    elif command == "list_names":
        names = Username.select()
        for name in names:
            print(f"{name.username}: {name.worker.hashed_id}")
    elif command == "id_lookup":
        worker_name = leaderboard.LookupUsernameFromId(id)
        print(worker_name)
    elif command == "hash_lookup":  
        worker_name = leaderboard.LookupUsernameFromMd5sum(hash)
        print(worker_name)
    elif command == "reverse_hash":
        worker_id = ReverseHash(hash, workers_file)
        print(worker_id)
    elif command == "reverse_name":
        worker_id = ReverseUsername(name, workers_file)
        print(worker_id)
    elif command == "calc_hash":
        md5sum = hashlib.md5(id.encode('utf-8')).hexdigest()
        print(md5sum)
    else:
        PrintUsage()

if __name__ == "__main__":
    fire.Fire(main)
