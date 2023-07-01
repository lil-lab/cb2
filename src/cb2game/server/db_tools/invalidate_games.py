""" Permanently modifies the database to invalidate certain games. Proceed with caution! """

import fire
import schemas.defaults
import schemas.game
from config.config import Config
from schemas import base
from schemas.game import Game


# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    with open(config_path, "r") as cfg_file:
        config = Config.from_json(cfg_file.read())
        return config


def main(from_id=0, to_id=0, config_path="config/server-config.json"):
    config = ReadConfigOrDie(config_path)

    print(f"Reading database from {config.database_path()}")
    # Setup the sqlite database used to record game actions.
    base.SetDatabase(config)
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    print(f"Invalidating games from {from_id} to {to_id}")
    games = Game.select().where(Game.id >= from_id, Game.id <= to_id).order_by(Game.id)
    for game in games:
        print(f"Invalidating game {game.id}...")
        game.valid = False
        game.save()

    print(f"Done.")


if __name__ == "__main__":
    fire.Fire(main)
