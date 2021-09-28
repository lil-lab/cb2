using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class FixedMapSource : HexGridManager.IMapSource
{
    public static Tile GroundTile()
    {
        return new Tile() {
            AssetId = UnityAssetSource.GROUND_TILE,
            RotationDegrees = 0,
            Edges = 0,
        };
    }

    public class Tile
    {
        public int AssetId;
        public int RotationDegrees;
        public byte Edges;
    }

    private List<HexGridManager.TileInformation> _map;
    private int _width, _height;

    private int _mapIteration = 0;

    public FixedMapSource(Tile[,] mapInfo)
    {
        _height = mapInfo.GetLength(0);
        _width = mapInfo.GetLength(1);
        _map = new List<HexGridManager.TileInformation>();

        for (int r = 0; r < mapInfo.GetLength(0); ++r)
        {
            for (int c = 0; c < mapInfo.GetLength(1); ++c)
            {
                Tile tileInfo = mapInfo[r, c];
                int hexA = r % 2;
                int hexR = r / 2;
                int hexC = c;
                HecsCoord coord = new HecsCoord(hexA, hexR, hexC);
                _map.Add(new HexGridManager.TileInformation
                {
                    Cell = new HexCell(coord, HexBoundary.FromBinary(tileInfo.Edges)),
                    AssetId = tileInfo.AssetId,
                    RotationDegrees = tileInfo.RotationDegrees
                });
            }
        }
        ++_mapIteration;
    }

    // Retrieves the dimensions of the hexagon grid.
    public (int, int) GetMapDimensions()
    {
        return (_height, _width);
    }

    // List of tiles. Each tile represents one cell in the grid.
    public List<HexGridManager.TileInformation> GetTileList()
    {
        return _map;
    }

    // Returns an integer. Increments each time any change is made to the map.
    // If the iteration remains unchanged, no map updates need to be done.
    // Technically there's a race condition between this and GetGrid.
    // TODO(sharf): update this interface to be atomic with GetGrid().
    // Worst case with this race, too much rendering is done, or an update
    // comes a bit late.
    public int GetMapIteration()
    {
        return _mapIteration;
    }
}
