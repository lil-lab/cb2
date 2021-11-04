using System;
using System.Collections.Generic;

namespace Network
{
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
            public int AssetId;
            public HexCell Cell;
            public int RotationDegrees;  // Multiple of 60 for grid alignment.
            public float Height;
        }

        public int Rows;
        public int Cols;

        // Tiles.
        public Tile[] Tiles;

        // Prop initial states.
        public List<Network.Prop> Props;
    }
}  // namespace Network