from datetime import datetime

import orjson
from map_provider import HardcodedMapProvider


def write_map_to_file(filename, map_update):
    """Writes json MapUpdate object to the given filename."""
    with open(filename, "w") as f:
        map_update_str = orjson.dumps(
            map_update,
            option=orjson.OPT_PASSTHROUGH_DATETIME | orjson.OPT_INDENT_2,
            default=datetime.isoformat,
        ).decode("utf-8")
        f.write(map_update.to_json())


def save_default_map():
    map_provider = HardcodedMapProvider()
    map_update = map_provider.get_map()
    write_map_to_file("map_update.json", map_update)
