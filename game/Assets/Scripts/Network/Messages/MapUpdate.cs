using System;
using System.Collections.Generic;

namespace Network
{

    [Serializable]
    public class Tile
    {
        // The ID of the asset for this ground tile. See IAssetSource.
        public int asset_id;
        public HexCell cell;
        public int rotation_degrees;  // Multiple of 60 for grid alignment.
        public float height;
    }


    [Serializable]
    public class City
    {
        public int r;
        public int c;
        public int size;
    }

    [Serializable]
    public enum LakeType
    {
        RANDOM = 0,
        L_SHAPED,
        ISLAND,
        REGULAR,
    }

    [Serializable]
    public class Lake
    {
        public int r;
        public int c;
        public int size;
        public LakeType type;
    }

    // An enum for different mountain types.
    public enum MountainType
    {
        NONE = 0,
        SMALL = 1,
        MEDIUM = 2,
        LARGE = 3
    }



    [Serializable]
    public class Mountain
    {
        public int r;
        public int c;
        public MountainType type;
        public bool snowy;
    }

    [Serializable]
    public class Outpost
    {
        public int r;
        public int c;
        public HecsCoord connection_a;
        public HecsCoord connection_b;
        public List<Tile> tiles;
    }

    [Serializable]
    public class MapMetadata
    {
        public List<Lake> lakes;
        public List<Mountain> mountains;
        public List<City> cities;
        public List<Outpost> outposts;
        public int num_partitions;
        public List<HecsCoord> partition_locations;
        public List<int> partition_sizes;
    }

    // A MapUpdate consists of a list of Tiles and Props. The Map is a 2D tiling
    // grid of hexagons, and Tiles describe each hexagon individually.
    // Props are objects located on the tiles, such as forests, trees, stones,
    // houses, cards and more.
    [Serializable]
    public class MapUpdate
    {

        public int rows;
        public int cols;

        // Tiles.
        public Tile[] tiles;

        public MapMetadata metadata;
    }
}  // namespace Network