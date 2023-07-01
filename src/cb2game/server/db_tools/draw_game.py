import fire
import schemas.map
from config.config import Config
from map_tools.visualize import draw_map_and_wait, sys
from schemas import base


# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    with open(config_path, "r") as cfg_file:
        config = Config.from_json(cfg_file.read())
        return config


def main(game_id, config_path="config/server-config.json"):
    """Read game map data from the database and draw it to the screen."""
    config = ReadConfigOrDie(config_path)

    # Setup the sqlite database used to record game actions.
    base.SetDatabase(config)
    base.ConnectDatabase()
    # base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    game_id = sys.argv[1]
    game_record = (
        schemas.game.Game.select().where(schemas.game.Game.id == game_id).get()
    )
    map_records = game_record.map_updates
    for map_record in map_records:
        map_update = map_record.map_data
        draw_map_and_wait(map_update)


if __name__ == "__main__":
    fire.Fire(main)
