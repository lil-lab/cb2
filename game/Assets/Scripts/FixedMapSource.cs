using System;
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

        mapInfo[8, 8] = FixedMapSource.MountainTile();
        mapInfo[9, 8] = FixedMapSource.MountainTile();
        mapInfo[9, 9] = FixedMapSource.MountainTile();
        mapInfo[9, 8] = FixedMapSource.RampToMountain();
        
        return mapInfo;
    }

    private static Tile GroundTile()
    {
        return new Tile() {
            AssetId = IAssetSource.AssetId.GROUND_TILE,
            RotationDegrees = 0,
            Edges = 0,
            Height = 0,
            Layer = 0,
        };
    }

    private static Tile GroundTileRocky()
    {
        return new Tile() {
            AssetId = IAssetSource.AssetId.GROUND_TILE_ROCKY,
            RotationDegrees = 0,
            Edges = 0x3f,
            Height = 0,
            Layer = 0,
        };
    }

    private static Tile GroundTileStones()
    {
        return new Tile() {
            AssetId = IAssetSource.AssetId.GROUND_TILE_STONES,
            RotationDegrees = 0,
            Edges = 0x3f,
            Height = 0,
            Layer = 0,
        };
    }

    private static Tile GroundTileTrees()
    {
        return new Tile() {
            AssetId = IAssetSource.AssetId.GROUND_TILE_TREES,
            RotationDegrees = 0,
            Edges = 0x3f,
            Height = 0,
            Layer = 0,
        };
    }
    private static Tile GroundTileSingleTree()
    {
        return new Tile() {
            AssetId = IAssetSource.AssetId.GROUND_TILE_TREES_2,
            RotationDegrees = 0,
            Edges = 0x3f,
            Layer = 0,
        };
    }
    private static Tile GroundTileForest()
    {
        return new Tile() {
            AssetId = IAssetSource.AssetId.GROUND_TILE_FOREST,
            RotationDegrees = 0,
            Edges = 0x3f,
            Height = 0,
            Layer = 0,
        };
    }
    private static Tile GroundTileHouse()
    {
        return new Tile()
        {
            AssetId = IAssetSource.AssetId.GROUND_TILE_HOUSE,
            RotationDegrees = 0,
            Edges = 0x3f,
            Height = 0,
            Layer = 0,
        };
    }
    private static Tile GroundTileStreetLight()
    {
        return new Tile() {
            AssetId = IAssetSource.AssetId.GROUND_TILE_STREETLIGHT,
            RotationDegrees = 0,
            Edges = 0x3f,
            Height = 0,
            Layer = 0,
        };
    }
    private static Tile MountainTile()
    {
        return new Tile() {
            AssetId = IAssetSource.AssetId.MOUNTAIN_TILE,
            RotationDegrees = 0,
            Edges = 0x00,
            Height = 0.325f,
            Layer = 2,
        };
    }
    private static Tile RampToMountain()
    {
        return new Tile() {
            AssetId = IAssetSource.AssetId.RAMP_TO_MOUNTAIN,
            RotationDegrees = 0,
            Edges = 0b101101,
            Height = 0.275f,
            Layer = 1,
        };
    }

    private class Tile
    {
        public IAssetSource.AssetId AssetId;
        public int RotationDegrees;
        public byte Edges;

        // Height is the Y-displacement of the tile (how high to place objects
		// on the tile).
        public float Height = 0;
        // Layer is the index height of the tile. This is an integer 
	    // categorization of height. For example, 0 = ground, 1 = ramp,
	    // 2 = mountain.
        public int Layer = 0;
    }

    private List<HexGridManager.TileInformation> _map;
    private int _width, _height;

    private bool _isMapFresh;

    public FixedMapSource()
    {
        var mapInfo = FixedMap();
        _height = mapInfo.GetLength(0);
        _width = mapInfo.GetLength(1);
        _map = new List<HexGridManager.TileInformation>();

        for (int r = 0; r < _height; ++r)
        {
            for (int c = 0; c < _width; ++c)
            {
                Tile tileInfo = mapInfo[r, c];
                HecsCoord coord = HecsCoord.FromOffsetCoordinates(r, c);
                HexBoundary boundary = HexBoundary.FromBinary(tileInfo.Edges);
                _map.Add(new HexGridManager.TileInformation
                {
                    Cell = new HexCell(coord, HexBoundary.FromBinary(tileInfo.Edges), tileInfo.Height, tileInfo.Layer),
                    AssetId = tileInfo.AssetId,
                    RotationDegrees = tileInfo.RotationDegrees,
                });
            }
        }

        // Add boundaries on the edge of the map.
        for (int i = 0; i < _map.Count; i++)
        {
            // For each neighbor which is out of bounds, add a boundary.
            HecsCoord loc = _map[i].Cell.coord;
	        foreach (HecsCoord n in loc.Neighbors())
            {
                (int nr, int nc) = n.ToOffsetCoordinates();
                // If the neighbor cell is outside the map.
		        if ((nr < 0) || (nc < 0) || (nr >= mapInfo.GetLength(0)) || (nc >= mapInfo.GetLength(1)))
                {
                    _map[i].Cell.boundary.SetEdgeWith(loc, n);
		        }
	        } 
	    }

        // Adds edges between adjacent cells that are on far-apart layers.
        AddLayerEdges();

        _isMapFresh = true;
    }

    // Adds edges between mountains and ground.
    private void AddLayerEdges()
    {
        // For any two adjacent cells A, B, adds an edge between A and B if their layer values differ by more than 1.
        // Ground has a layer of 0, the ramp has a layer of 1, and mountains have a layer of 2.
        for (int i = 0; i < _map.Count; ++i)
        {
	        for (int j = 0; j < _map.Count; ++j)
            {
                if (i == j) continue;
                if (!_map[i].Cell.coord.IsAdjacentTo(_map[j].Cell.coord)) continue;

                // _map[i] and _map[j] are adjacent and i != j.
                int layer_diff = Math.Abs(_map[i].Cell.layer - _map[j].Cell.layer);
                if (layer_diff > 1)
                {
                    // Only need to add the edge to _map[i]. The HexGridManager adds edge symmetry later.
                    _map[i].Cell.boundary.SetEdgeWith(_map[i].Cell.coord, _map[j].Cell.coord); 
		        }
	        }
	    }
    }

    // Retrieves the dimensions of the hexagon grid.
    public (int, int) GetMapDimensions()
    {
        return (_height, _width);
    }

    // List of tiles. Each tile represents one cell in the grid.
    public List<HexGridManager.TileInformation> FetchTileList()
    {
        _isMapFresh = false;
        return _map;
    }

    // TODO(sharf): update this interface to be atomic with FetchGrid().
    // Worst case with this race, too much rendering is done, or an update
    // comes a bit late.
    public bool IsMapReady()

    {
        return _isMapFresh;
    }
}
