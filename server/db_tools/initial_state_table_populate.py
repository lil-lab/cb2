from playhouse.sqlite_ext import CSqliteExtDatabase
import peewee
from server.hex import HecsCoord
import server.schemas.defaults as defaults_db


import server.db_tools.db_utils as db_utils
import server.config.config as config
import server.messages.message_from_server as message_from_server

from server.messages.logs import LogEntry, Direction, GameInfo
from server.schemas.game import Game, InitialState
from server.schemas.game import Move
from server.schemas import base
from server.messages.rooms import Role

import fire
import json
import logging
import os
import pathlib

logger = logging.getLogger(__name__)

game_directories = {}

def InitGameDirectories(config):
    record_base_dir = pathlib.Path(config.record_directory())
    games = os.listdir(record_base_dir)
    for game in games:
        try:
            id = int(game.split("_")[1])
            game_directories[id] = record_base_dir / game
        except ValueError:
            pass

def GameDirectory(game_id):
    if game_id not in game_directories:
        logger.warning(f"Could not find game directory for game {game_id}")
        return None
    return game_directories[game_id]

def main(config_filepath="server/config/server-config.json"):
    logging.basicConfig(level=logging.INFO)
    cfg = config.ReadConfigOrDie(config_filepath)

    InitGameDirectories(cfg)

    print(f"Reading database from {cfg.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(cfg.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(defaults_db.ListDefaultTables())

    games = db_utils.ListMturkGames()

    # Make sure the user wants to continue after listing games.
    print("Games: " + (", ".join([str(g.id) for g in games])))
    print("Continue? (y/n)")
    if input() != "y":
        return

    # For each game.
    mismatch = False
    for game in games:
        logger.info(f"Processing game {game.id}")

        # Find game logs.
        game_dir = GameDirectory(game.id)

        if game_dir == None:
            logger.warning(f"Could not find game directory for game {game.id}")
            # If the game ID is >= 2000, pause and confirm with the user.
            if game.id >= 2000:
                print(f"Could not find game directory for game {game.id}. Anything other than 'Quit' will continue.")
                if input() == "Quit":
                    return
            continue

        game_info = game_dir / "game_info.jsonl.log" 

        leader_id = -1
        follower_id = -1
        with game_info.open() as f:
            game_info = GameInfo.from_json(f.read())
            for id, role in zip(game_info.ids, game_info.roles):
                if role == Role.LEADER:
                    leader_id = id
                elif role == Role.FOLLOWER:
                    follower_id = id

        if leader_id == -1 or follower_id == -1:
            logger.warning(f"Could not find leader/follower IDs for game {game.id}")
            # If the game ID is >= 2000, pause and confirm with the user.
            if game.id >= 2126:
                print(f"Could not find leader/follower IDs for game {game.id}. Anything other than 'Quit' will continue.")
                if input() == "Quit":
                    return
            continue

        # Find all the messages from the server.
        messages_from_server_file = game_dir / "messages_from_server.jsonl.log"

        messages_from_server = []
        with messages_from_server_file.open() as f:
            for line in f:
                try:
                    message = json.loads(line)
                except json.decoder.JSONDecodeError:
                    logger.warning(f"Could not decode message from server for game {game.id}")
                    continue
                if message["message_direction"] == Direction.FROM_SERVER.value:
                    messages_from_server.append(message["message_from_server"])
                else:
                    logger.warning(f"Wrong dir: {message['message_direction']}. FROM_SERVER: {Direction.FROM_SERVER}")

        if len(messages_from_server) == 0:
            logger.warning(f"No messages from server for game {game.id}")
            if game.id >= 2126:
                return
            continue

        # Find the first message that is a state sync.
        state_sync = None
        for message in messages_from_server:
            if message["type"] == message_from_server.MessageType.STATE_SYNC.value:
                state_sync = message["state"]
                break
        
        if state_sync == None:
            logger.warning(f"Could not find state sync for game {game.id}. Anything other than 'Quit' will continue.")
            if game.id >= 2126:
                return
            continue
        
        leader_starting_pos = None
        leader_starting_orientation = None
        follower_starting_pos = None
        follower_starting_orientation = None
        for actor in state_sync["actors"]:
            if actor["actor_id"] == leader_id:
                moves = Move.select().where(Move.game_id == game.id, Move.character_role == "Role.LEADER").order_by(Move.id)
            if actor["actor_id"] == follower_id:
                moves = Move.select().where(Move.game_id == game.id, Move.character_role == "Role.FOLLOWER").order_by(Move.id)
            if moves.count() == 0:
                print(f"Game {game.id} has no moves for actor {actor['actor_id']}")
            location = actor["location"]
            location_hex = HecsCoord(location["a"], location["r"], location["c"]) 
            if moves.count() != 0 and moves.get().position_before != location_hex:
                print(f"Game {game.id} has a MISMATCH between the state sync and the first move for actor {actor['actor_id']}")
                mismatch = True
                return
            if actor["actor_id"] == leader_id:
                leader_starting_pos = location_hex
                leader_starting_orientation = actor["rotation_degrees"]
            if actor["actor_id"] == follower_id:
                follower_starting_pos = location_hex
                follower_starting_orientation = actor["rotation_degrees"]
        
        # Add entry to the InitialState table.
        if leader_starting_pos != None and follower_starting_pos != None:
            initial_state_query = InitialState.select().where(InitialState.game_id == game.id)
            if initial_state_query.count() == 0:
                initial_state = InitialState(
                    game_id=game.id,
                    leader_id = leader_id,
                    follower_id = follower_id,
                    leader_position = leader_starting_pos,
                    leader_rotation_degrees = leader_starting_orientation,
                    follower_position = follower_starting_pos,
                    follower_rotation_degrees = follower_starting_orientation
                )
                initial_state.save()
            else:
                initial_state = initial_state_query.get()
                if initial_state.leader_position != leader_starting_pos or initial_state.leader_rotation_degrees != leader_starting_orientation or initial_state.follower_position != follower_starting_pos or initial_state.follower_rotation_degrees != follower_starting_orientation:
                    print(f"Game {game.id} has a MISMATCH between the state sync and the initial state")
                    mismatch = True
                    return
            logger.info(f"Added initial state for game {game.id}. Leader pos: {leader_starting_pos}, rot: {leader_starting_orientation}, Follower pos: {follower_starting_pos}, rot: {follower_starting_orientation}")

    print("Done")
    if mismatch:
        print("There were mismatches.")
    else:
        print("No mismatches.")

if __name__ == "__main__":
    fire.Fire(main)