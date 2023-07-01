""" This file takes the CB2 sqlite database and converts it to a json file.

    We release our data in both sqlite and json formats. The sqlite format is
    easier to work with for our internal tools, but the json format is easier
    for external users to work with.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List

import fire
from mashumaro import DataClassDictMixin

from cb2game.server.schemas import base
from cb2game.server.schemas.event import Event
from cb2game.server.schemas.game import Game
from cb2game.server.util import JsonSerialize

logger = logging.getLogger(__name__)


def SwitchToDatabase(db):
    base.SetDatabaseByPath(db)
    base.ConnectDatabase()


@dataclass
class JsonEventSchema(DataClassDictMixin):
    """Schema for the json event format.

    This is a JSON clone of the Event dataclass, with some fields renamed for
    clarity. The JSON format is easier to work with for some users.

    For documentation of this schema, see the Event dataclass in
    `server/schemas/event.py`.
    """

    id: str
    game: int
    type: str
    turn_number: int
    tick: int
    server_time: float
    client_time: float
    origin: str
    role: str
    parent_event_id: int
    data: dict
    short_code: str
    location: dict
    orientation: dict


@dataclass
class JsonGameSchema(DataClassDictMixin):
    """Schema for the json game format.

    This is a JSON clone of the Game dataclass, with some fields omitted or
    renamed for clarity.

    For documentation of this schema, see the Game dataclass in
    `server/schemas/game.py`.
    """

    id: int
    type: str
    score: int
    start_time: str
    end_time: str
    events: List[JsonEventSchema]
    kvals: Dict[str, str]


def ConvertEventToDataclass(event: Event):
    """For each event, list the:"""
    return JsonEventSchema(
        id=event.id,
        game=event.game_id,
        type=event.type,
        turn_number=event.turn_number,
        tick=event.tick,
        server_time=event.server_time,
        client_time=event.client_time,
        origin=event.origin,
        role=event.role,
        parent_event_id=event.parent_event_id,
        data=event.data,
        short_code=event.short_code,
        location=event.location,
        orientation=event.orientation,
    )


def ConvertGameToDataclass(game: Game):
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
    return JsonGameSchema(
        id=game.id,
        type=game.type,
        score=game.score,
        start_time=game.start_time,
        end_time=game.end_time,
        events=[ConvertEventToDataclass(event) for event in game_events],
        kvals=game.kvals,
    )


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
    games = [ConvertGameToDataclass(game) for game in games]

    # Write the json file.
    print(f"Writing {len(games)} games to {json_path}...")
    with open(json_path, "w") as f:
        output_string = JsonSerialize(games, pretty=pretty)
        f.write(output_string)


if __name__ == "__main__":
    fire.Fire(main)
