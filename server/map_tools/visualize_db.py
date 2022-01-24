from map_tools.visualize import *
import schemas.map
from schemas import base
from config.config import Config
from map_utils import FloodFillPartitionTiles

# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    with open(config_path, 'r') as cfg_file:
        config = Config.from_json(cfg_file.read())
        return config

def main():
    """ Reads a JSON bug report from a file provided on the command line and displays the map to the user. """
    # Check that the correct number of arguments were provided.
    if len(sys.argv) != 2:
        print("Usage: python visualize_db.py <map_id> {<config_path>}")
        quit()

    config_path = "config/server-config.json" if len(sys.argv) <= 2 else sys.argv[2]
    config = ReadConfigOrDie(config_path)

    # Setup the sqlite database used to record game actions.
    base.SetDatabase(config.database_path())
    base.ConnectDatabase()
    # base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())

    map_id = sys.argv[1]
    map_record = schemas.map.MapUpdate.select().where(
        schemas.map.MapUpdate.id == map_id).get()
    map_update = map_record.map_data
    partitions = FloodFillPartitionTiles(map_update.tiles)
    print(len(partitions))
    draw_map_and_wait(map_update)

if __name__ == "__main__":
    main()
