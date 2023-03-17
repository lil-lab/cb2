""" This file takes the CB2 sqlite database and converts it to a json file.

    We release our data in both sqlite and json formats. The sqlite format is
    easier to work with for our internal tools, but the json format is easier
    for external users to work with.
"""

import json
import logging

import fire

from server.schemas import base
from server.schemas.event import Event
from server.schemas.game import Game
from server.util import JsonSerialize

logger = logging.getLogger(__name__)


def SwitchToDatabase(db):
    base.SetDatabaseByPath(db)
    base.ConnectDatabase()


def ConvertEventToDict(event):
    """For each event, list the:
    ID,
    Type,
    Data,
    Short Code
    Parent ID
    Time
    Turn Number
    Location
    Orientation

    In a dictionary.
    """
    return {
        "id": event.id,
        "game": event.game.id,
        "type": event.type,
        "turn_number": event.turn_number,
        "tick": event.tick,
        "server_time": event.server_time,
        "client_time": event.client_time,
        "origin": event.origin,
        "role": event.role,
        "parent_id": event.parent_event_id,
        "data": json.loads(event.data) if event.data else None,
        "short_code": event.short_code,
        "location": event.location,
        "orientation": event.orientation,
    }


def ConvertGameToDict(game: Game):
    """Get the game's list of events. Convert the game to a structure with this information:

    ID
    type
    score
    start_time
    end_time
    completed
    events: List[Event]
    """
    game_events = list(Event.select().where(Event.game == game.id))
    return {
        "id": game.id,
        "type": game.type,
        "score": game.score,
        "start_time": game.start_time,
        "end_time": game.end_time,
        "events": [ConvertEventToDict(event) for event in game_events],
    }


def main(db_path, json_path, pretty: bool = True):
    logging.basicConfig(level=logging.INFO)
    logger.info(f"DB to JSON")

    logger.info(f"Opening DB...")
    SwitchToDatabase(db_path)
    database = base.GetDatabase()

    print(f"Loading data from {db_path}...")
    with database.connection_context():
        # Query all games.
        print(f"Querying all games...")
        games = list(Game.select().where(Game.id).order_by(Game.id))

    print(f"Converting {len(games)} games to json...")

    # Convert each game to a dictionary.
    games = [ConvertGameToDict(game) for game in games]

    print(f"Type of games[0]: {type(games[0])}")

    # Write the json file.
    print(f"Writing {len(games)} games to {json_path}...")
    with open(json_path, "w") as f:
        output_string = JsonSerialize(games, pretty=pretty)
        f.write(output_string)


if __name__ == "__main__":
    fire.Fire(main)
