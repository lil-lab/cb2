""" Code for updating experience entries. """
import logging

import cb2game.server.schemas.mturk as mturk_db

logger = logging.getLogger(__name__)


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


def update_leader_stats(leader_experience, game_record):
    logger.info(f"update_leader_stats(score={game_record.score})")
    if len(leader_experience.last_1k_lead_scores) > 1000:
        logger.warning(
            f"Leader experience entry {leader_experience.id} has more than 1000 lead scores. Truncating."
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
            f"Leader experience entry {leader_experience.id} has more than 1000 scores. Truncating."
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


def update_follower_stats(follower_experience, game_record):
    logger.info(f"update_follower_stats(score={game_record.score})")
    if len(follower_experience.last_1k_follow_scores) > 1000:
        logger.warning(
            f"Follower experience entry {follower_experience.id} has more than 1000 follow scores. Truncating."
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
            f"Leader experience entry {follower_experience.id} has more than 1000 scores. Truncating."
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


def InitExperience(experience):
    """Initializes a worker's experience table."""
    experience = mturk_db.WorkerExperience.create()

    experience.lead_games_played = 0
    experience.lead_score_sum = 0
    experience.lead_score_avg = 0

    experience.follow_games_played = 0
    experience.follow_score_sum = 0
    experience.follow_score_avg = 0

    experience.total_games_played = 0
    experience.total_score_sum = 0
    experience.total_score_avg = 0

    experience.last_1k_lead_scores = []
    experience.last_1k_follow_scores = []
    experience.last_1k_scores = []

    experience.last_lead = None
    experience.last_follow = None
    experience.last_game = None

    experience.save()
    return experience
