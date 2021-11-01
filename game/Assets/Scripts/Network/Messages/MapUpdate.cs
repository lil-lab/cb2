using System;

namespace Network
{
    [Serializable]
    public class MapUpdate
    {
        [Serializable]
        public class Tile
        {
			public int AssetId;
			public HexCell Cell;
			public int RotationDegrees;  // Multiple of 60 for grid alignment.
			public float Height;
        }

        public int Rows;
        public int Cols;
        public Tile[] Tiles;
    }
}  // namespace Network