import hashlib
import pathlib
import sys

import fire
import humanhash
from sparklines import sparklines

import server.config.config as config
import server.leaderboard as leaderboard
import server.schemas.defaults as defaults_db
from server.db_tools import db_utils
from server.schemas import base
from server.schemas.google_user import GoogleUser
from server.schemas.leaderboard import Username
from server.schemas.mturk import Worker, WorkerExperience, WorkerQualLevel

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
    "prodigious_leaders",  # Prints workers who haven't played much (< 3 lead games), but have a high lead score. (top 30%)
    "good_followers",  # Prints workers who have played >= N follower games with average >= N points (threshold).
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
    print(
        "  ldrbrd workers_by_experience [--role=leader|follower|both] [--nosparklines]"
    )
    print("  ldrbrd hopeless_leaders [--nosparklines]")
    print("  ldrbrd prodigious_leaders [--nosparklines]")
    print("  ldrbrd good_followers --threshold=N [--nosparklines]")
    print(
        "  ldrbrd qual --role=expert|leader|follower|none|noop --workers_file=<filepath>"
    )
    print("  ldrbrd list_google")
    print("  ldrbrd help")


def PrintGoogleAccounts(tutorial_progress: bool):
    """Prints all google accounts."""
    google_users = GoogleUser.select()
    for google_user in google_users:
        if tutorial_progress:
            print(
                f"id: {google_user.id} id_hash: {google_user.hashed_google_id}, tutorial_progress: {google_user.kv_store}"
            )
        else:
            print(f"email: {google_user.hashed_google_id}")


def ReverseHash(worker_hash, workers_file):
    path = pathlib.PosixPath(workers_file).expanduser()
    with path.open() as wlist:
        for worker in wlist:
            worker = worker.strip()
            md5sum = hashlib.md5(worker.encode("utf-8")).hexdigest()
            if worker_hash is not None:
                if md5sum == worker_hash:
                    return worker


def ReverseUsername(worker_name, workers_file):
    path = pathlib.PosixPath(workers_file).expanduser()
    with path.open() as wlist:
        for worker in wlist:
            worker = worker.strip()
            md5sum = hashlib.md5(worker.encode("utf-8")).hexdigest()
            name = humanhash.humanize(md5sum, words=2)
            if worker_name is not None:
                if name == worker_name:
                    return worker


def PrintWorkerExperienceEntries(entries, role, no_sparklines):
    for entry in entries:
        avg_metric = {
            "leader": entry.lead_score_avg,
            "follower": entry.follow_score_avg,
            "both": entry.total_score_avg,
            "noop": entry.total_score_avg,
        }.get(role, "ERR")
        num_games_metric = {
            "leader": entry.lead_games_played,
            "follower": entry.follow_games_played,
            "both": entry.total_games_played,
            "noop": entry.total_games_played,
        }.get(role, "ERR")
        recent_games = {
            "leader": entry.last_1k_lead_scores,
            "follower": entry.last_1k_follow_scores,
            "both": entry.last_1k_scores,
            "noop": entry.last_1k_scores,
        }.get(role, [])
        if entry.worker.exists():
            print(
                f"hash: {entry.worker.get().hashed_id}, role: {role}, avg score: {avg_metric:.2f}, num games: {num_games_metric}"
            )
        if not no_sparklines:
            for line in sparklines(recent_games, num_lines=2, minimum=0, maximum=30):
                print(line)


def PrintWorkersRanked(role, no_sparklines):
    """Prints workers by avg score."""
    experience_entries = []
    if role == "leader":
        experience_entries = WorkerExperience.select().order_by(
            WorkerExperience.lead_score_avg.desc()
        )
    elif role == "follower":
        experience_entries = WorkerExperience.select().order_by(
            WorkerExperience.follow_score_avg.desc()
        )
    elif role == "both":
        experience_entries = WorkerExperience.select().order_by(
            WorkerExperience.total_score_avg.desc()
        )
    elif role == "noop":
        experience_entries = WorkerExperience.select().order_by(
            WorkerExperience.total_score_avg.desc()
        )
    else:
        print("Invalid role: " + role)
        return

    # Filter out non-active workers.
    experience_entries = [entry for entry in experience_entries]

    PrintWorkerExperienceEntries(experience_entries, role, no_sparklines)


def PrintWorkersByExperience(role, no_sparklines):
    """Prints workers by # of games rather than avg score."""
    experience_entries = []
    if role == "leader":
        experience_entries = WorkerExperience.select().order_by(
            WorkerExperience.lead_games_played.desc()
        )
    elif role == "follower":
        experience_entries = WorkerExperience.select().order_by(
            WorkerExperience.follow_games_played.desc()
        )
    elif role == "both":
        experience_entries = WorkerExperience.select().order_by(
            WorkerExperience.total_games_played.desc()
        )
    elif role == "noop":
        experience_entries = WorkerExperience.select().order_by(
            WorkerExperience.total_games_played.desc()
        )
    else:
        print("Invalid role: " + role)
        return

    # Filter out non-active workers.
    experience_entries = [entry for entry in experience_entries]

    PrintWorkerExperienceEntries(experience_entries, role, no_sparklines)


def PrintHopelessLeaders(no_sparklines):
    """Prints workers who have played > 10 lead games but have a low lead score. (bottom 30% of *all* players)."""
    # Get workers by avg lead score (ascending).
    experience_entries = WorkerExperience.select().order_by(
        WorkerExperience.lead_score_avg
    )

    # Determine the bottom 30% of workers by avg lead score.
    bottom_30_percent = int(len(experience_entries) * 0.3)
    experience_entries = experience_entries[:bottom_30_percent]

    # Filter out new workers.
    experience_entries = [
        entry for entry in experience_entries if entry.lead_games_played > 10
    ]

    print("Hopeless leaders:")
    PrintWorkerExperienceEntries(experience_entries, "leader", no_sparklines)


def PrintProdigiousLeaders(no_sparklines):
    """Prints workers who haven't played much (< 3 games) but have a high lead score. (top 30% of *all* players)."""
    # Get workers by avg lead score (descending).
    experience_entries = WorkerExperience.select().order_by(
        WorkerExperience.lead_score_avg.desc()
    )

    # Determine the top 30% of workers by avg lead score.
    top_30_percent = int(len(experience_entries) * 0.3)
    experience_entries = experience_entries[:top_30_percent]

    # Filter out old workers.
    experience_entries = [
        entry for entry in experience_entries if entry.lead_games_played < 3
    ]

    print("Prodigious workers:")
    PrintWorkerExperienceEntries(experience_entries, "leader", no_sparklines)


def PrintGoodFollowers(no_sparklines, threshold):
    """Prints out followers that have more than threshold games with score >= threshold."""
    # Get workers by avg follower score (descending).
    experience_entries = WorkerExperience.select().order_by(
        WorkerExperience.follow_score_avg.desc()
    )

    # Filter out old workers.
    experience_entries = [
        entry
        for entry in experience_entries
        if entry.follow_games_played >= threshold
        and entry.follow_score_avg >= threshold
    ]

    print("Good followers:")
    PrintWorkerExperienceEntries(experience_entries, "follower", no_sparklines)


def PrintWorkerQualification(worker_hashes):
    """Prints out the qualification status of the provided worker hashes."""
    print("Printing Worker Qualifications...")
    for hash in worker_hashes:
        worker = Worker.select().where(Worker.hashed_id == hash)
        if worker.count() == 0:
            print(f"Worker {hash} not found.")
            continue
        worker = worker.get()
        qual_level = worker.qual_level
        if qual_level == None:
            print(f"Worker {hash} has no qual level.")
            continue
        qual = WorkerQualLevel(qual_level)
        print(f"{hash}: {qual.name}")


def SetUserQualifications(role, workers_file):
    """Sets the given qualification for the given workers."""
    path = pathlib.PosixPath(workers_file).expanduser()
    with path.open() as wlist:
        worker_ids = [line.strip() for line in wlist]

    worker_hashes = [
        hashlib.md5(worker_id.encode("utf-8")).hexdigest() for worker_id in worker_ids
    ]

    if role == "noop":
        PrintWorkerQualification(worker_hashes)
        return

    qual_level = {
        "leader": WorkerQualLevel.LEADER,
        "follower": WorkerQualLevel.FOLLOWER,
        "expert": WorkerQualLevel.EXPERT,
        "none": WorkerQualLevel.NONE,
    }[role]

    for worker_hash in worker_hashes:
        worker = Worker.select().where(Worker.hashed_id == worker_hash)
        if worker.count() == 0:
            print(f"Worker {worker_hash} not found! Created.")
            worker = Worker.create(hashed_id=worker_hash, qual_level=int(qual_level))
            worker.save()
        else:
            worker = worker.get()
            worker.qual_level = int(qual_level)
            worker.save()
        print(f"Set {worker.hashed_id} qual_level to {qual_level.name}")


def main(
    command,
    id="",
    hash="",
    name="",
    workers_file="",
    item="",
    role="noop",
    nosparklines=False,
    threshold=3,
    config_filepath="server/config/server-config.yaml",
):
    if command == "help":
        PrintUsage()
        return

    cfg = config.ReadConfigOrDie(config_filepath)

    print(f"Reading database from {cfg.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(cfg)
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(defaults_db.ListDefaultTables())

    if command == "list":
        board = leaderboard.GetLeaderboard()
        for i, entry in enumerate(board):
            leader_name = leaderboard.LookupUsername(entry.leader)
            follower_name = leaderboard.LookupUsername(entry.follower)
            print(
                f"{i:3}: scr: {entry.score} ldr: {leader_name} flwr: {follower_name} time: {entry.time}"
            )
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
        md5sum = hashlib.md5(id.encode("utf-8")).hexdigest()
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
    elif command == "qual":
        SetUserQualifications(role, workers_file)
    elif command == "list_google":
        PrintGoogleAccounts(tutorial_progress=True)
    else:
        PrintUsage()


if __name__ == "__main__":
    fire.Fire(main)
