""" Code for updating the worker experience table. """
import logging

import peewee

import server.schemas.mturk as mturk_db
from server.experience import InitExperience, update_follower_stats, update_leader_stats

logger = logging.getLogger()


def GetOrCreateWorkerExperienceEntry(worker_hashed_id):
    worker_query = (
        mturk_db.Worker.select()
        .join(mturk_db.WorkerExperience, join_type=peewee.JOIN.LEFT_OUTER)
        .where(mturk_db.Worker.hashed_id == worker_hashed_id)
    )
    if worker_query.count() == 0:
        logger.warning(
            f"Worker {worker_hashed_id} does not exist in the database. Skipping."
        )
        return None
    worker = worker_query.get()
    if worker.experience is None:
        worker.experience = mturk_db.WorkerExperience.create()
        worker.experience.save()
        worker.save()
    return worker.experience


def GetWorkerExperienceEntry(worker_hashed_id):
    worker_query = (
        mturk_db.Worker.select()
        .join(mturk_db.WorkerExperience, join_type=peewee.JOIN.LEFT_OUTER)
        .where(mturk_db.Worker.hashed_id == worker_hashed_id)
    )
    if worker_query.count() == 0:
        logger.warning(
            f"Worker {worker_hashed_id} does not exist in the database. Skipping."
        )
        return None
    worker = worker_query.get()
    return worker.experience


def InitWorkerExperience(worker):
    """Initializes a worker's experience table."""
    worker.experience = InitExperience()
    worker.save()


def UpdateLeaderExperience(game_record):
    # Update leader lead & total scores.
    if game_record.leader is None:
        return
    leader_experience = GetOrCreateWorkerExperienceEntry(game_record.leader.hashed_id)
    if leader_experience is None:
        return
    print(f"Leader EXP ID: {leader_experience.id}")
    update_leader_stats(leader_experience, game_record)


def UpdateFollowerExperience(game_record):
    # Update follower follow & total scores.
    if game_record.follower is None:
        return
    follower_experience = GetOrCreateWorkerExperienceEntry(
        game_record.follower.hashed_id
    )
    if follower_experience is None:
        return
    print(f"Follower EXP ID: {follower_experience.id}")
    update_follower_stats(follower_experience, game_record)


def UpdateWorkerExperienceTable(game_record):
    """Given a game record (joined with leader & followers) updates leader & follower experience table."""
    if "game-mturk" not in game_record.type:
        # Only update the leader & follower experience table for mturk games.
        return
    UpdateLeaderExperience(game_record)
    UpdateFollowerExperience(game_record)
