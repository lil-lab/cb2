# Creates a set of graphics where an instruction is displayed on the left, and
# the follower's pathway is displayed on the right.
import logging
import random

import fire

from cb2game.server.config.config import Config, ReadConfigOrDie
from cb2game.server.db_tools import db_utils
from cb2game.server.messages.objective import ObjectiveMessage
from cb2game.server.schemas import base
from cb2game.server.schemas.defaults import ListDefaultTables
from cb2game.server.schemas.event import Event, EventType
from cb2game.server.schemas.game import Game

logger = logging.getLogger(__name__)


def main(
    number=-1,
    search_term="",
    research_only=True,
    config_filepath="",
):
    logging.basicConfig(level=logging.INFO)
    if config_filepath == "":
        config = Config()
        logger.warning(
            f"No config was provided. Using default database located at: {config.database_path()}"
        )
    else:
        config = ReadConfigOrDie(config_filepath)

    print(f"Reading database from {config.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(config)
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(ListDefaultTables())

    games = (
        db_utils.ListAnalysisGames(config)
        if research_only
        else db_utils.ListMturkGames()
    )
    words = set()
    instruction_list = []
    for game in games:
        instructions = (
            Event.select()
            .where(Event.type == EventType.INSTRUCTION_SENT)
            .join(Game)
            .where(Event.game == game)
        )
        for instruction in instructions:
            decoded_data = ObjectiveMessage.from_json(instruction.data)
            text = decoded_data.text
            if len(search_term) > 0 and search_term in text:
                print(f"Search term found in game {game.id}: {text}")
            words.update(text.split(" "))
            instruction_list.append(text)

    if number < 0:
        number = len(instruction_list)
    sample = random.sample(instruction_list, min(number, len(instruction_list)))
    if len(search_term) == 0:
        for instruction in sample:
            print(instruction)


if __name__ == "__main__":
    fire.Fire(main)
