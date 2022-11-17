""" Code for updating the Google user experience table. """
import logging

import peewee

import server.schemas.google_user as google_db
from server.experience import InitExperience, update_follower_stats, update_leader_stats
from server.lobby_consts import LobbyType
from server.schemas.mturk import WorkerExperience

logger = logging.getLogger()


def GetOrCreateUserExperienceEntry(hashed_user_id):
    user_query = (
        google_db.GoogleUser.select()
        .join(WorkerExperience, join_type=peewee.JOIN.LEFT_OUTER)
        .where(google_db.GoogleUser.hashed_google_id == hashed_user_id)
    )
    if user_query.count() == 0:
        logger.warning(
            f"User {hashed_user_id} does not exist in the database. Skipping."
        )
        return None
    user = user_query.get()
    if user.experience is None:
        user.experience = WorkerExperience.create()
        user.experience.save()
        user.save()
    return user.experience


def GetUserExperienceEntry(hashed_user_id):
    user_query = (
        google_db.GoogleUser.select()
        .join(WorkerExperience, join_type=peewee.JOIN.LEFT_OUTER)
        .where(google_db.GoogleUser.hashed_google_id == hashed_user_id)
    )
    if user_query.count() == 0:
        logger.warning(
            f"User {google_user_id} does not exist in the database. Skipping."
        )
        return None
    user = user_query.get()
    return user.experience


def InitUserExperience(user):
    """Initializes a worker's experience table."""
    user.experience = InitExperience()
    user.save()


def UpdateLeaderExperience(game_record):
    # Update leader lead & total scores.
    if game_record.leader is None:
        return
    leader_experience = GetOrCreateUserExperienceEntry(game_record.leader.hashed_id)
    if leader_experience is None:
        return
    print(f"Leader EXP ID: {leader_experience.id}")
    update_leader_stats(leader_experience, game_record)


def UpdateFollowerExperience(game_record):
    # Update follower follow & total scores.
    if game_record.follower is None:
        return
    follower_experience = GetOrCreateUserExperienceEntry(game_record.follower.hashed_id)
    if follower_experience is None:
        return
    print(f"Follower EXP ID: {follower_experience.id}")
    update_follower_stats(follower_experience, game_record)


def UpdateGoogleUserExperienceTable(game_record):
    """Given a game record (joined with leader & followers) updates leader & follower experience table."""
    game_type_components = game_record.type.split("|")
    if len(game_type_components) < 3:
        return
    (lobby_name, lobby_type, game_type) = game_type_components
    if game_type == "game":
        # Only update the leader & follower experience table for games.
        return
    if lobby_type != str(LobbyType.GOOGLE):
        # Only update the leader & follower experience table for google games.
        return
    UpdateLeaderExperience(game_record)
    UpdateFollowerExperience(game_record)
