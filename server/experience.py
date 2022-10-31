""" Code for updating the worker experience table. """
import logging

import peewee

import server.schemas.mturk as mturk_db

logger = logging.getLogger()


def GetWorkerExperienceEntries():
    """Returns a list of all worker experience entries sorted by # of games."""
    return mturk_db.WorkerExperience.select().order_by(
        mturk_db.WorkerExperience.total_games_played.desc()
    )


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


def update_game_stats(sum, count, avg, recent_scores, game_score):
    """Updates the game stats for a given game. Utility function for this file only, primarily used by UpdateWorkerExperienceTable."""
    sum += game_score
    count += 1
    avg = sum / count

    recent_scores = list(recent_scores)

    if len(recent_scores) == 1000:
        recent_scores.pop(0)

    recent_scores.append(game_score)

    return (sum, count, avg, recent_scores)


def InitWorkerExperience(worker):
    """Initializes a worker's experience table."""
    worker.experience = mturk_db.WorkerExperience.create()

    worker.experience.lead_games_played = 0
    worker.experience.lead_score_sum = 0
    worker.experience.lead_score_avg = 0

    worker.experience.follow_games_played = 0
    worker.experience.follow_score_sum = 0
    worker.experience.follow_score_avg = 0

    worker.experience.total_games_played = 0
    worker.experience.total_score_sum = 0
    worker.experience.total_score_avg = 0

    worker.experience.last_1k_lead_scores = []
    worker.experience.last_1k_follow_scores = []
    worker.experience.last_1k_scores = []

    worker.experience.last_lead = None
    worker.experience.last_follow = None
    worker.experience.last_game = None

    worker.experience.save()
    worker.save()


def UpdateLeaderExperience(game_record):
    # Update leader lead & total scores.
    if game_record.leader is None:
        return
    leader_experience = GetOrCreateWorkerExperienceEntry(game_record.leader.hashed_id)
    if leader_experience is None:
        return
    print(f"Leader EXP ID: {leader_experience.id}")

    if len(leader_experience.last_1k_lead_scores) > 1000:
        logger.warning(
            f"Leader experience entry {game_record.leader.hashed_id} has more than 1000 lead scores. Truncating."
        )
        leader_experience.last_1k_lead_scores = leader_experience.last_1k_lead_scores[
            -1000:
        ]
    (
        leader_experience.lead_score_sum,
        leader_experience.lead_games_played,
        leader_experience.lead_score_avg,
        leader_experience.last_1k_lead_scores,
    ) = update_game_stats(
        leader_experience.lead_score_sum,
        leader_experience.lead_games_played,
        leader_experience.lead_score_avg,
        leader_experience.last_1k_lead_scores,
        game_record.score,
    )
    if len(leader_experience.last_1k_scores) > 1000:
        logger.warning(
            f"Leader experience entry {game_record.leader.hashed_id} has more than 1000 scores. Truncating."
        )
        leader_experience.last_1k_scores = leader_experience.last_1k_scores[-1000:]
    (
        leader_experience.total_score_sum,
        leader_experience.total_games_played,
        leader_experience.total_score_avg,
        leader_experience.last_1k_scores,
    ) = update_game_stats(
        leader_experience.total_score_sum,
        leader_experience.total_games_played,
        leader_experience.total_score_avg,
        leader_experience.last_1k_scores,
        game_record.score,
    )

    if (leader_experience.last_lead is None) or (
        game_record.start_time > leader_experience.last_lead.start_time
    ):
        leader_experience.last_lead = game_record
    if (leader_experience.last_game is None) or (
        game_record.start_time > leader_experience.last_game.start_time
    ):
        leader_experience.last_game = game_record
    leader_experience.save()


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

    if len(follower_experience.last_1k_follow_scores) > 1000:
        logger.warning(
            f"Follower experience entry {game_record.follower.hashed_id} has more than 1000 follow scores. Truncating."
        )
        follower_experience.last_1k_follow_scores = (
            follower_experience.last_1k_follow_scores[-1000:]
        )
    (
        follower_experience.follow_score_sum,
        follower_experience.follow_games_played,
        follower_experience.follow_score_avg,
        follower_experience.last_1k_follow_scores,
    ) = update_game_stats(
        follower_experience.follow_score_sum,
        follower_experience.follow_games_played,
        follower_experience.follow_score_avg,
        follower_experience.last_1k_follow_scores,
        game_record.score,
    )
    if len(follower_experience.last_1k_scores) > 1000:
        logger.warning(
            f"Leader experience entry {game_record.follower.hashed_id} has more than 1000 scores. Truncating."
        )
        follower_experience.last_1k_scores = follower_experience.last_1k_scores[-1000:]
    (
        follower_experience.total_score_sum,
        follower_experience.total_games_played,
        follower_experience.total_score_avg,
        follower_experience.last_1k_scores,
    ) = update_game_stats(
        follower_experience.total_score_sum,
        follower_experience.total_games_played,
        follower_experience.total_score_avg,
        follower_experience.last_1k_scores,
        game_record.score,
    )

    if (follower_experience.last_follow is None) or (
        game_record.start_time > follower_experience.last_follow.start_time
    ):
        follower_experience.last_follow = game_record
    if (follower_experience.last_game is None) or (
        game_record.start_time > follower_experience.last_game.start_time
    ):
        follower_experience.last_game = game_record
    follower_experience.save()


def UpdateWorkerExperienceTable(game_record):
    """Given a game record (joined with leader & followers) updates leader & follower experience table."""
    if game_record.type != "game-mturk":
        # Only update the leader & follower experience table for mturk games.
        return
    UpdateLeaderExperience(game_record)
    UpdateFollowerExperience(game_record)
