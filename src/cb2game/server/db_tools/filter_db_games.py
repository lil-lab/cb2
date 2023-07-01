""" This script iterates through an SQL database and filters out games that are
not in the provided list. """

import logging

import fire

from cb2game.server.schemas import base
from cb2game.server.schemas.game import Game

logger = logging.getLogger(__name__)


def SwitchToDatabase(db):
    base.SetDatabaseByPath(db)
    base.ConnectDatabase()


def DeleteEvents(game):
    """Delete all events for a game.

    One issue is that many events have foreign keys to other events. This
    function first wipes all of the foreign keys for any event in a game, then
    deletes the events.

    The foreign keys are in the event.parent_event field.
    """
    for event in game.events:
        event.parent_event = None
        event.save()

    for event in game.events:
        event.delete_instance()


def DeleteGame(game):
    """Delete a game and all of its events."""
    DeleteEvents(game)
    game.delete_instance()


def main(db_path, good_game_ids_path):
    logging.basicConfig(level=logging.INFO)
    logger.info(f"Opening game ID path.")

    good_game_ids = []
    # IDs are comma-separated, all on one line.
    with open(good_game_ids_path, "r") as f:
        good_game_ids = [int(id) for id in f.read().split(",")]

    logger.info(f"Opening DB...")
    SwitchToDatabase(db_path)
    database = base.GetDatabase()

    print(f"Loading data from {db_path}...")
    with database.connection_context():
        # Query all games.
        print(f"Querying all games...")
        games = list(Game.select().where(Game.id).order_by(Game.id))

        # Identify which games are to be deleted.
        print(f"Identifying games to delete...")
        games_to_delete = [game for game in games if game.id not in good_game_ids]

        games_which_stay = [game for game in games if game.id in good_game_ids]

        # Print the number of games to delete, the number of remaining games,
        # and the percentage of games that will be deleted.
        num_games_to_delete = len(games_to_delete)
        num_games_which_stay = len(games_which_stay)
        percent_games_to_delete = num_games_to_delete / (
            num_games_to_delete + num_games_which_stay
        )
        print(f"Number of games to be deleted: {num_games_to_delete}")
        print(f"Number of games which stay: {num_games_which_stay}")
        print(f"Percentage of games to be deleted: {percent_games_to_delete}")

        # Ask the user if they want to delete the games.
        print(f"Are you sure you want to delete these games? (y/n)")
        user_input = input()
        if user_input != "y":
            print(f"Exiting.")
            return

        # Double check that the user wants to delete the games.
        print(f"Are you really sure you want to delete these games? (y/n)")
        user_input = input()
        if user_input != "y":
            print(f"Exiting.")
            return

        # Delete the games.
        print(f"Deleting games...")
        for game in games_to_delete:
            DeleteGame(game)


if __name__ == "__main__":
    fire.Fire(main)
