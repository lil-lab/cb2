using System.Collections;
using System.Collections.Generic;
using UnityEngine;

// This class provides a fixed, built-in map for testing. The map layout is
// defined in static function FixedMap() at the top of the class.
public class FixedMapSource : HexGridManager.IMapSource
{
    // This is where the map is defined.
    private static FixedMapSource.Tile[,] FixedMap()
    {
        FixedMapSource.Tile[,] mapInfo = new FixedMapSource.Tile[20, 20];
        for (int i = 0; i < 20; ++i)
        {
            for (int j = 0; j < 20; ++j)
            {
                mapInfo[i,j] = FixedMapSource.GroundTile();
            }
        }
        
        mapInfo[10, 10] = FixedMapSource.GroundTileForest();
        mapInfo[10, 11] = FixedMapSource.GroundTileHouse();
        mapInfo[11, 11] = FixedMapSource.GroundTileStones();
        mapInfo[11, 10] = FixedMapSource.GroundTileStreetLight();
        mapInfo[9, 10] = FixedMapSource.GroundTileSingleTree();
        
        return mapInfo;
    }

    private static Tile GroundTile()
    {
        return new Tile() {
            AssetId = UnityAssetSource.Assets.GROUND_TILE,
            RotationDegrees = 0,
            Edges = 0,
        };
    }

    private static Tile GroundTileRocky()
    {
        return new Tile() {
            AssetId = UnityAssetSource.Assets.GROUND_TILE_ROCKY,
            RotationDegrees = 0,
            Edges = 0x3f,
        };
    }

    private static Tile GroundTileStones()
    {
        return new Tile() {
            AssetId = UnityAssetSource.Assets.GROUND_TILE_STONES,
            RotationDegrees = 0,
            Edges = 0x3f,
        };
    }

    private static Tile GroundTileTrees()
    {
        return new Tile() {
            AssetId = UnityAssetSource.Assets.GROUND_TILE_TREES,
            RotationDegrees = 0,
            Edges = 0x3f,
        };
    }
    private static Tile GroundTileSingleTree()
    {
        return new Tile() {
            AssetId = UnityAssetSource.Assets.GROUND_TILE_TREES_2,
            RotationDegrees = 0,
            Edges = 0x3f,
        };
    }
    private static Tile GroundTileForest()
    {
        return new Tile() {
            AssetId = UnityAssetSource.Assets.GROUND_TILE_FOREST,
            RotationDegrees = 0,
            Edges = 0x3f,
        };
    }
    private static Tile GroundTileHouse()
    {
        return new Tile()
        {
            AssetId = UnityAssetSource.Assets.GROUND_TILE_HOUSE,
            RotationDegrees = 0,
            Edges = 0x3f,
        };
    }
    private static Tile GroundTileStreetLight()
    {
        return new Tile() {
            AssetId = UnityAssetSource.Assets.GROUND_TILE_STREETLIGHT,
            RotationDegrees = 0,
            Edges = 0x3f,
        };
    }

    private class Tile
    {
        public UnityAssetSource.Assets AssetId;
        public int RotationDegrees;
        public byte Edges;
    }

    private List<HexGridManager.TileInformation> _map;
    private int _width, _height;

    private int _mapIteration = 0;

    public FixedMapSource()
    {
        var mapInfo = FixedMap();
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
                    AssetId = (int)tileInfo.AssetId,
                    RotationDegrees = tileInfo.RotationDegrees,
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
