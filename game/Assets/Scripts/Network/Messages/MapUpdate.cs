using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class MapMetadata
    {
        public int num_cities;
        public int num_lakes;
        public int num_mountains;
        public int num_outposts;
    }

    // A MapUpdate consists of a list of Tiles and Props. The Map is a 2D tiling
    // grid of hexagons, and Tiles describe each hexagon individually.
    // Props are objects located on the tiles, such as forests, trees, stones,
    // houses, cards and more.
    [Serializable]
    public class MapUpdate
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

        public int rows;
        public int cols;

        // Tiles.
        public Tile[] tiles;

        // Prop initial states.
        public List<Network.Prop> props;
        public MapMetadata metadata;
    }
}  // namespace Network