from dataclasses import dataclass, field
from typing import List, Tuple

from mashumaro.mixins.json import DataClassJSONMixin

from cb2game.server.assets import AssetNamesFromTileClass, TileClass


def default_asset_names(tile_class: TileClass) -> List[str]:
    return field(default_factory=lambda: AssetNamesFromTileClass(tile_class))


@dataclass(frozen=True)
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
    # These lists allow specifying which tiles are used in map generation.  Each
    # list forms an equivalency class of tiles which are functionally the same.
    # See AssetsFromTileClass in map_utils.py for a list of asset classes
    # See AssetId in assets.py for a list of all assets.
    # If unspecified, the default for each list is all assets.
    #
    # In certain cases, the map generation algorithm may have a preference for a
    # single tile in a class. If that tile is available, it is always chosen. If
    # it isn't, an equivalent tile is chosen at random. In cases where the
    # algorithm has no preference, a tile is chosen at random from the class.
    ground_tiles: List[str] = default_asset_names(TileClass.GROUND_TILES)
    path_tiles: List[str] = default_asset_names(TileClass.PATH_TILES)
    stone_tiles: List[str] = default_asset_names(TileClass.STONE_TILES)
    foliage_tiles: List[str] = default_asset_names(TileClass.FOLIAGE_TILES)
    tree_tiles: List[str] = default_asset_names(TileClass.TREE_TILES)
    streetlight_tiles: List[str] = default_asset_names(TileClass.STREETLIGHT_TILES)
    # House tiles used in outposts (i.e. not in city centers, may extend in future).
    house_tiles: List[str] = default_asset_names(TileClass.HOUSE_TILES)
    # Houses specifically used in city centers (i.e. not in outposts).
    urban_house_tiles: List[str] = default_asset_names(TileClass.URBAN_HOUSE_TILES)
    water_tiles: List[str] = default_asset_names(TileClass.WATER_TILES)
