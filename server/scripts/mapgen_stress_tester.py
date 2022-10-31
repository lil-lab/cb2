import time

import fire
from map_provider import MapProvider, MapType


def main(number_maps=100):
    # Generate number_maps number of random maps.
    start_time = time.time()
    for i in range(number_maps):
        map_provider = MapProvider(MapType.RANDOM)
        map = map_provider.map()
        print(f"Generated map {i}: map: {map}")
    end_time = time.time()
    print(f"Generated {number_maps} maps in {end_time - start_time} seconds.")
    print(f"Time per map: {(end_time - start_time) / number_maps}")


if __name__ == "__main__":
    fire.Fire(main)
