""" A tool which scans each game in the database to validate the live feedback.

This is because of a discovery that the server previously did not validate live feedback.

Makes sure that live feedback was only sent during the follower's turn.

"""

import fire

import cb2game.server.schemas.base as base
from cb2game.server.config.config import ReadConfigOrDie
from cb2game.server.schemas import base
from cb2game.server.schemas.game import Game, LiveFeedback, Move


def main(config_filepath=""):
    config = ReadConfigOrDie(config_filepath)

    # Connect to the database.
    base.SetDatabase(config)
    base.ConnectDatabase()

    games_with_invalid_live_feedback = []
    for game in Game.select():
        try:
            turn_times = {}  # Maps turn number to (start_time, end_time)
            events = []  # (game_time, move_role)
            for move in game.moves.order_by(Move.game_time):
                events.append((move.game_time, move.character_role))

            # Sort events by game_time.
            events.sort(key=lambda x: x[0])

            # For each feedback, make sure that it happened next to a follower move.
            for feedback in game.feedbacks.order_by(LiveFeedback.game_time):
                # Find the move that happened next to this feedback.
                for i in range(len(events)):
                    if events[i][0] > feedback.game_time:
                        break

                # Make sure that the event was not sandwiched between two leader moves.
                next_event_leader = (
                    events[i][1] == "Role.LEADER" if i + 1 < len(events) else False
                )
                prev_event_leader = (
                    events[i - 1][1] == "Role.LEADER" if i - 1 >= 0 else False
                )
                if next_event_leader and prev_event_leader:
                    games_with_invalid_live_feedback.append(game.id)
        except Exception:
            continue

    print(
        f"{len(games_with_invalid_live_feedback)} Games with invalid live feedback: {games_with_invalid_live_feedback}"
    )
    print(f"Total number of games: {Game.select().count()}")


if __name__ == "__main__":
    fire.Fire(main)
