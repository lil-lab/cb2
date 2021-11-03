from messages import map_update
from map_provider import HardcodedMapProvider

def write_map_to_file(filename, map_update):
    """ Writes json MapUpdate object to the given filename. """
    with open(filename, 'w') as f:
        f.write(map_update.to_json())

def save_default_map():
    map_provider = HardcodedMapProvider()
    map_update = map_provider.get_map()
    write_map_to_file('map_update.json', map_update)