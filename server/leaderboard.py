""" Code for updating the leaderboard table. """
import hashlib

import humanhash

import server.schemas.leaderboard as leaderboard_db
import server.schemas.mturk as mturk_db
from server.username_word_list import USERNAME_WORDLIST


def GetLeaderboard():
    """Returns a list of the top 10 leaderboard entries."""
    return (
        leaderboard_db.Leaderboard.select()
        .order_by(leaderboard_db.Leaderboard.score.desc())
        .limit(10)
    )


def UpdateLeaderboard(game_record):
    """Updates the leaderboard table with the latest score."""
    if game_record.type == "game-mturk":
        if game_record.score > 0:
            leaderboard_entry = leaderboard_db.Leaderboard.create(
                time=game_record.end_time,
                score=game_record.score,
                leader=game_record.leader,
                follower=game_record.follower,
            )
            leaderboard_entry.save()
        # If there are now more than 10 entries, delete the one with the lowest score.
        if leaderboard_db.Leaderboard.select().count() > 10:
            lowest_entry = (
                leaderboard_db.Leaderboard.select()
                .order_by(leaderboard_db.Leaderboard.score.asc())
                .get()
            )
            lowest_entry.delete_instance()


def LookupUsername(worker):
    """Returns the username for a given worker."""
    username_select = leaderboard_db.Username.select().where(
        leaderboard_db.Username.worker == worker
    )
    if username_select.count() == 0:
        return None
    return username_select.get().username


def LookupUsernameFromId(worker_id):
    md5sum = hashlib.md5(worker_id.encode("utf-8")).hexdigest()
    return LookupUsernameFromMd5sum(md5sum)


def LookupUsernameFromMd5sum(worker_id_md5sum):
    worker_select = mturk_db.Worker.select().where(
        mturk_db.Worker.hashed_id == worker_id_md5sum
    )
    if worker_select.count() == 0:
        return None
    return LookupUsername(worker_select.get())


def SetUsername(worker, username):
    """Sets the username for a given worker."""
    username_select = leaderboard_db.Username.select().where(
        leaderboard_db.Username.worker == worker
    )
    if username_select.count() == 0:
        username_entry = leaderboard_db.Username.create(
            username=username, worker=worker
        )
        username_entry.save()
    else:
        username_select.get().username = username
        username_select.get().save()


def SetDefaultUsername(worker):
    """Uses humanhash to generate a default 2 word username based on the worker's hashed_id. Adds it to the Username table."""
    hasher = humanhash.HumanHasher(wordlist=USERNAME_WORDLIST)
    username = hasher.humanize(worker.hashed_id, words=2)
    SetUsername(worker, username)
