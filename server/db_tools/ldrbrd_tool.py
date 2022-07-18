from schemas.mturk import Worker
from schemas.leaderboard import Username

import config.config as config
import experience
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

from sparklines import sparklines

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
    "workers_ranked",  # Ranks workers by score.
    "workers_by_experience",  # Ranks workers by # of games played.
    "hopeless_leaders",  # Prints workers who have played > 10 lead games but have a low lead score. (bottom 30%)
    "prodigious_leaders", # Prints workers who haven't played much (< 3 lead games), but have a high lead score. (top 30%)
    "good_followers",     # Prints workers who have played > N follower games with > N points (threshold).
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
    print("  ldrbrd workers_ranked [--role=leader|follower|both] [--nosparklines]")
    print("  ldrbrd workers_by_experience [--role=leader|follower|both] [--nosparklines]")
    print("  ldrbrd hopeless_leaders [--nosparklines]")
    print("  ldrbrd prodigious_leaders [--nosparklines]")
    print("  ldrbrd good_followers --threshold=N [--nosparklines]")
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

def PrintWorkerExperienceEntries(entries, role, no_sparklines):
    for entry in entries:
        avg_metric = {
            "leader": entry.lead_score_avg,
            "follower": entry.follower_score_avg,
            "both": entry.total_score_avg
        }.get(role, "ERR")
        num_games_metric = {
            "leader": entry.lead_games_played,
            "follower": entry.follow_games_played,
            "both": entry.total_games_played
        }.get(role, "ERR")
        recent_games = {
            "leader": entry.last_100_lead_scores,
            "follower": entry.last_100_follow_scores,
            "both": entry.last_100_scores
        }.get(role, [])
        print(f"hash: {entry.worker.hashed_id[0:6]}, role: {role}, avg score: {avg_metric:.2f}, num games: {num_games_metric}")
        if not no_sparklines:
            for line in sparklines(recent_games, num_lines=2):
                print(line)

def PrintWorkersRanked(role, no_sparklines):
    """ Prints workers by avg score. """
    experience_entries = []
    if role == "leader":
        experience_entries = schemas.mturk.WorkerExperience.select().order_by(schemas.mturk.WorkerExperience.lead_score_avg.desc())
    elif role == "follower":
        experience_entries = schemas.mturk.WorkerExperience.select().order_by(schemas.mturk.WorkerExperience.follower_score_avg.desc())
    elif role == "both":
        experience_entries = schemas.mturk.WorkerExperience.select().order_by(schemas.mturk.WorkerExperience.total_score_avg.desc())
    else:
        print("Invalid role: " + role)
        return
    
    PrintWorkerExperienceEntries(experience_entries, role, no_sparklines)
        

def PrintWorkersByExperience(role, no_sparklines):
    """ Prints workers by # of games rather than avg score. """
    experience_entries = []
    if role == "leader":
        experience_entries = schemas.mturk.WorkerExperience.select().order_by(schemas.mturk.WorkerExperience.lead_games_played.desc())
    elif role == "follower":
        experience_entries = schemas.mturk.WorkerExperience.select().order_by(schemas.mturk.WorkerExperience.follow_games_played.desc())
    elif role == "both":
        experience_entries = schemas.mturk.WorkerExperience.select().order_by(schemas.mturk.WorkerExperience.total_games_played.desc())
    else:
        print("Invalid role: " + role)
        return

    PrintWorkerExperienceEntries(experience_entries, role, no_sparklines)

def PrintHopelessLeaders(no_sparklines):
    """ Prints workers who have played > 10 lead games but have a low lead score. (bottom 30% of *all* players)."""
    # Get workers by avg lead score (ascending).
    experience_entries = schemas.mturk.WorkerExperience.select().order_by(schemas.mturk.WorkerExperience.lead_score_avg)

    # Determine the bottom 30% of workers by avg lead score.
    bottom_30_percent = int(len(experience_entries) * 0.3)
    experience_entries = experience_entries[:bottom_30_percent]

    # Filter out new workers.
    experience_entries = [entry for entry in experience_entries if entry.lead_games_played > 10]

    print("Hopeless leaders:")
    PrintWorkerExperienceEntries(experience_entries, "leader", no_sparklines)

def PrintProdigiousLeaders(no_sparklines):
    """ Prints workers who haven't played much (< 3 games) but have a high lead score. (top 30% of *all* players)."""
    # Get workers by avg lead score (descending).
    experience_entries = schemas.mturk.WorkerExperience.select().order_by(schemas.mturk.WorkerExperience.lead_score_avg.desc())

    # Determine the top 30% of workers by avg lead score.
    top_30_percent = int(len(experience_entries) * 0.3)
    experience_entries = experience_entries[:top_30_percent]

    # Filter out old workers.
    experience_entries = [entry for entry in experience_entries if entry.lead_games_played < 3]

    print("Prodigious workers:")
    PrintWorkerExperienceEntries(experience_entries, "leader", no_sparklines)

def PrintGoodFollowers(no_sparklines, threshold):
    """ Prints out followers that have more than threshold games with score >= threshold. """
    # Get workers by avg follower score (descending).
    experience_entries = schemas.mturk.WorkerExperience.select().order_by(schemas.mturk.WorkerExperience.follower_score_avg.desc())

    # Filter out old workers.
    experience_entries = [entry for entry in experience_entries if entry.follow_games_played > threshold]

    print("Good followers:")
    PrintWorkerExperienceEntries(experience_entries, "follower", no_sparklines)

def main(command, id="", hash="", name="", workers_file = "", item="", role="both", nosparklines=False, threshold=3, config_filepath="config/server-config.json"):
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
    elif command == "workers_ranked":
        PrintWorkersRanked(role, nosparklines)
    elif command == "workers_by_experience":
        PrintWorkersByExperience(role, nosparklines)
    elif command == "hopeless_leaders":
        PrintHopelessLeaders(nosparklines)
    elif command == "prodigious_leaders":
        PrintProdigiousLeaders(nosparklines)
    elif command == "good_followers":
        PrintGoodFollowers(nosparklines, threshold)
    else:
        PrintUsage()

if __name__ == "__main__":
    fire.Fire(main)
