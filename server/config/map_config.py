from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class MapConfig(DataClassJSONMixin):
    """Configuration for the map generator.

    Currently used to specify which assets are allowed to be used in the map.

    Assets are categorized by equivalence class. See the asset class enum in assets.py.
    """

    map_width: int = 25
    map_height: int = 25
    # These are specified as tuples (min, max) (integers only)
    number_of_mountains_range: Tuple[int, int] = (3, 3)
    number_of_cities_range: Tuple[int, int] = (3, 4)
    number_of_lakes_range: Tuple[int, int] = (3, 4)
    number_of_outposts_range: Tuple[int, int] = (3, 6)
    # How close two feature points need to be in order to be path-routed
    # together by the path generation algorithm. Unit is distance in map-tile diameters.
    path_connection_distance: int = 4
    # List of which assets the mapgen algorithm can use.
    assets_enabled: Dict[str, List[str]] = field(default_factory={"": []})
