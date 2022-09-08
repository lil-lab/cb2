""" Yikes, I forgot to introduce a column in the instructions DB for cancelled instructions.

    This is because cancelled instructions didn't exist originally, and when I added them, I never added any code to log it in the DB.

    This script will go through all the games and calculate cancelled
    instructions and fill them in the DB, similar to integrate_orientation.
    Pretty happy with my decision to log all client-server messages as it saves
    me in situations like this (this is actually exactly why I did that).
"""

from email import message
from multiprocessing.sharedctypes import Value
import peewee
import server.schemas.defaults as defaults_db

from server.schemas import base
from server.schemas.game import Instruction
from server.messages.message_from_server import MessageFromServer, MessageType
from server.messages.turn_state import TurnState
from server.messages.logs import LogEntry, Direction
from server.config import config

import fire
import sys
import json
import logging
import os
import pathlib
import sys

import server.db_tools.db_utils as db_utils

logger = logging.getLogger(__name__)

game_directories = {}

def InitGameDirectories(config):
    record_base_dir = pathlib.Path(config.record_directory())
    games = os.listdir(record_base_dir)
    for game in games:
        try:
            id = int(game.split("_")[1])
            logger.info(f"Found game logs for game {id}")
            game_directories[id] = record_base_dir / game
        except ValueError:
            pass

def GameDirectory(game_id):
    if game_id not in game_directories:
        logger.warning(f"Could not find game directory for game {game_id}")
        return None
    return game_directories[game_id]

def main(config_filepath="config/separated-games-2.json", no_i_totally_know_what_im_doing_i_swear=False):
    cfg = config.ReadConfigOrDie(config_filepath)
    print(f"Reading database from {cfg.database_path()}")

    logging.basicConfig(level=logging.INFO)

    # Warning to make sure the person running this reads this script first.
    if not no_i_totally_know_what_im_doing_i_swear:
        print("This script is a total hack. It was made once to recover lost orientation values. If you're relying on it, at least read the code first. To make this work, run via :\n\tpython3 -m db_tools.find_cancelled_instructions --no_i_totally_know_what_im_doing_i_swear")
        sys.exit(1)

    # Setup the sqlite database used to record game actions.
    base.SetDatabase(cfg.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(defaults_db.ListDefaultTables())

    InitGameDirectories(cfg)

    logger.info(f"Wiping all instruction cancelled data.")
    for instruction in Instruction.select():
        logger.info(f".")
        instruction.turn_cancelled = -1
        instruction.save()
    logger.info(f"Wiped!")

    games = db_utils.ListMturkGames()
    # For each game.
    for game in games:
        logger.info(f"Processing game {game.id}")

        # Find game logs.
        game_dir = GameDirectory(game.id)

        if game_dir == None:
            logger.warning(f"Could not find game directory for game {game.id}")
            continue

        # Find all the messages from the server.
        messages_from_server_file = game_dir / "messages_from_server.jsonl.log"

        messages_from_server = []
        with messages_from_server_file.open() as f:
            for line in f:
                message = json.loads(line)
                if message["message_direction"] == Direction.FROM_SERVER.value:
                    messages_from_server.append(message["message_from_server"])
        
        logger.info(f"Found {len(messages_from_server)} messages from server")
        
        turn_number = -1
        for message in messages_from_server:
            if message["type"] == MessageType.GAME_STATE.value:
                turn_number = message["turn_state"]["turn_number"]
            if message["type"] == MessageType.OBJECTIVE.value:
                for objective in message["objectives"]:
                    if objective["cancelled"]:
                        if turn_number == -1:
                            logger.warning(f"Found cancelled objective before game state. Game {game.id}")
                            continue;
                        instruction = Instruction.select().where(Instruction.uuid == objective["uuid"]).get()
                        if instruction.turn_completed != -1:
                            logger.warning(f"Found cancelled objective that was already completed. Game {game.id} instruction {instruction.uuid}")
                            instruction.turn_cancelled = -1
                            continue
                        if instruction.turn_cancelled != -1:
                            # Objectives, once cancelled, still appear in the objectives list. Don't overwrite the turn_cancelled for older instructions that we already ran into.
                            logger.warning(f"Found cancelled objective that was already cancelled. Game {game.id} instruction {instruction.uuid}")
                            continue
                        instruction.turn_cancelled = turn_number
                        instruction.save()
    logger.info(f"Finished processing games")

if __name__ == "__main__":
    fire.Fire(main)
