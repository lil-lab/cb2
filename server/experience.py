""" Code for updating the worker experience table. """
from turtle import update
from schemas.game import Game
import schemas.mturk

import hashlib
import humanhash
import logging

logger = logging.getLogger()

def GetWorkerExperienceEntries():
    """ Returns a list of all worker experience entries sorted by # of games. """
    return schemas.mturk.WorkerExperience.select().order_by(schemas.mturk.WorkerExperience.total_games_played.desc())

def GetOrCreateWorkerExperienceEntry(worker_hashed_ip):
    worker = schemas.mturk.Worker.select().join(schemas.mturk.WorkerExperience).where(schemas.mturk.Worker.hashed_ip == worker_hashed_ip).get()
    if worker.experience is None:
        worker.experience = schemas.mturk.WorkerExperience.create()
        worker.experience.save()
        worker.save()
    return worker.experience

def update_game_stats(sum, count, avg, recent_scores, game_score):
    """ Updates the game stats for a given game. Utility function for this file only, primarily used by UpdateWorkerExperienceTable. """
    sum += game_score
    count += 1
    avg = sum / count

    recent_scores = list(recent_scores)

    if len(recent_scores) == 100:
        recent_scores.pop(0)
    
    recent_scores.append(game_score)

    return (sum, count, avg, recent_scores)

def InitWorkerExperience(worker):
    """ Initializes a worker's experience table. """
    if worker.experience is None:
        worker.experience = schemas.mturk.WorkerExperience.create()

    worker.experience.lead_games_played = 0
    worker.experience.lead_score_sum = 0
    worker.experience.lead_score_avg = 0

    worker.experience.follow_games_played = 0
    worker.experience.follow_score_sum = 0
    worker.experience.follow_score_avg = 0

    worker.experience.total_games_played = 0
    worker.experience.total_score_sum = 0
    worker.experience.total_score_avg = 0

    worker.experience.last_100_lead_scores = []
    worker.experience.last_100_follow_scores = []
    worker.experience.last_100_scores = []
    worker.experience.save()
    worker.save()

def UpdateWorkerExperienceTable(game_record):
    """ Given a game record (joined with leader & followers) updates leader & follower experience table. """
    if game_record.type != 'game-mturk':
        # Only update the leader & follower experience table for mturk games.
        return

    # Update leader lead & total scores.
    leader_experience = GetOrCreateWorkerExperienceEntry(game_record.leader.hashed_ip)
    if len(leader_experience.last_100_lead_scores) > 100:
        logger.warning(f"Leader experience entry {game_record.leader.hashed_ip} has more than 100 lead scores. Truncating.")
        leader_experience.last_100_lead_scores = leader_experience.last_100_lead_scores[-100:]
    leader_experience.lead_score_sum, leader_experience.lead_games_played, leader_experience.lead_score_avg, leader_experience.last_100_lead_scores= update_game_stats(leader_experience.lead_score_sum, leader_experience.lead_games_played, leader_experience.lead_score_avg, leader_experience.last_100_lead_scores, game_record.score)
    if len(leader_experience.last_100_scores) > 100:
        logger.warning(f"Leader experience entry {game_record.leader.hashed_ip} has more than 100 scores. Truncating.")
        leader_experience.last_100_scores = leader_experience.last_100_scores[-100:]
    leader_experience.total_score_sum, leader_experience.total_games_played, leader_experience.total_score_avg, _ = update_game_stats(leader_experience.total_score_sum, leader_experience.total_games_played, leader_experience.total_score_avg, leader_experience.last_100_scores, game_record.score)
    leader_experience.save()

    # Update follower follow & total scores.
    follower_experience = GetOrCreateWorkerExperienceEntry(game_record.follower.hashed_ip)
    if len(follower_experience.last_100_follow_scores) > 100:
        logger.warning(f"Follower experience entry {game_record.follower.hashed_ip} has more than 100 follow scores. Truncating.")
        follower_experience.last_100_follow_scores = follower_experience.last_100_follow_scores[-100:]
    follower_experience.follow_score_sum, follower_experience.follow_games_played, follower_experience.follow_score_avg, follower_experience.last_100_follow_scores = update_game_stats(follower_experience.follow_score_sum, follower_experience.follow_games_played, follower_experience.follow_score_avg, follower_experience.last_100_follow_scores, game_record.score)
    if len(follower_experience.last_100_scores) > 100:
        logger.warning(f"Leader experience entry {game_record.follower.hashed_ip} has more than 100 scores. Truncating.")
        follower_experience.last_100_scores = follower_experience.last_100_scores[-100:]
    follower_experience.total_score_sum, follower_experience.total_games_played, follower_experience.total_score_avg, _ = update_game_stats(follower_experience.total_score_sum, follower_experience.total_games_played, follower_experience.total_score_avg, follower_experience.last_100_scores, game_record.score)
    follower_experience.save()