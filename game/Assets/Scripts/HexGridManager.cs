using System.Collections;
using System.Collections.Generic;
using UnityEngine;


// This class manages the hexagonal grid. It is responsible for pulling map
// updates from an IMapSource and then loading the required assets from an
// IAssetSource. These are specified via an interface to generically decouple
// this class from Asset and Map implementations (Dependency Injection).
//
// This class uses the Hexagon Efficient Coordinate System (HECS) as
// detailed in the following link. This means coordinates consist of 3
// parameters: A, R, C.
// https://en.wikipedia.org/wiki/Hexagonal_Efficient_Coordinate_System
public class HexGridManager
{
    public class TileInformation
    {
        public int AssetId;
        public HexCell Cell;
        public int RotationDegrees;  // Multiple of 60 for grid alignment.
    }

    public class Tile
    {
        public int AssetId;
        public HexCell Cell;
        public int RotationDegrees;  // Multiple of 60 for grid alignment.
        public GameObject Model;
    }

    // Interface for loading assets.
    public interface IAssetSource
    {
        // Returns a prefab of the requested asset.
        GameObject Load(int assetId);

        // TODO(sharf): If we want to remove unity-specific interfaces entirely,
        // this interface can be rewritten to add something similar to Unity's
        // "Instantiate" function. 
    }

    // Interface for retrieving map updates.
    public interface IMapSource
    {
        // Retrieves the dimensions of the hexagon grid. Returns (rows, cols).
        (int, int) GetMapDimensions();

        // List of tiles. Each tile represents one cell in the grid. Calling 
	    // this causes IsMapReady() to return false until the next map update is
	    // available.
        List<TileInformation> FetchTileList();

        // Returns true if a new map iteration is available.
        bool IsMapReady();
    }

    private IMapSource _mapSource;
    private IAssetSource _assetSource;

    // Used to determine if player can walk through an edge.
    private HexCell[,,] _edgeMap;

    // A list of all the tiles currently placed in the map.
    private Tile[,,] _grid;

    // If true, draws debug lines showing boundaries in the edge map.
    public bool _debugEdges = false;

    public HexGridManager(IMapSource mapSource, IAssetSource assetSource)
    {
        _mapSource = mapSource;
        _assetSource = assetSource;
    }

    public void Start()
    {
        (int rows, int cols) = _mapSource.GetMapDimensions();
        _grid = new Tile[2, rows / 2, cols];
        _edgeMap = new HexCell[2, rows / 2, cols];

        // Pre-initialize the edge map to be all-empty.
        for (int r = 0; r < rows; r++)
        {
            for (int c = 0; c < cols; c++)
            {
                int hecsA = r % 2;
                int hecsR = r / 2;
                int hecsC = c;

                _edgeMap[hecsA, hecsR, hecsC] = new HexCell(
                    new HecsCoord(hecsA, hecsR, hecsC), new HexBoundary());
            }
        }
    }

    public void Update()
    {
        UpdateMap();
        if (_debugEdges)
	    { 
	        foreach (HexCell c in _edgeMap)
		    {
                if (c.boundary.Serialize() == 0) continue;
                var vertices = c.Vertices();
                if (c.boundary.UpRight())
                {
                    Debug.DrawLine(vertices[0], vertices[1], Color.blue, 2.0f, true);
		        }
                if (c.boundary.Right())
                {
                    Debug.DrawLine(vertices[1], vertices[2], Color.green, 2.0f, true);
		        }
                if (c.boundary.DownRight())
                {
                    Debug.DrawLine(vertices[2], vertices[3], Color.magenta, 2.0f, true);
		        }
                if (c.boundary.DownLeft())
                {
                    Debug.DrawLine(vertices[3], vertices[4], Color.black, 2.0f, true);
		        }
                if (c.boundary.Left())
                {
                    Debug.DrawLine(vertices[4], vertices[5], Color.red, 2.0f, true);
		        }
                if (c.boundary.UpLeft())
                {
                    Debug.DrawLine(vertices[5], vertices[0], Color.white, 2.0f, true);
		        }
	        }    
	    }
    }

    public bool EdgeBetween(HecsCoord a, HecsCoord b)
    {
        return _edgeMap[a.a, a.r, a.c].boundary.GetEdgeWith(a, b);
    }

    public float Height(HecsCoord a)
    {
        return _grid[a.a, a.r, a.c].Cell.height;
    }

    public void DebugEdges(bool val)
    {
        _debugEdges = val; 
    }

    public HexCell Cell(HecsCoord a)
    {
        return _edgeMap[a.a, a.r, a.c];
    }

    private bool CoordInMap(HecsCoord c)
    {

        (int rows, int cols) = _mapSource.GetMapDimensions();
        if (c.r * 2 + c.a >= rows) return false;
        if (c.c >= cols) return false;
        if (c.a < 0) return false;
        if (c.r < 0) return false;
        if (c.c < 0) return false;
        return true;
    }

    // Updates the edge boundary map for a single cell.
    private void UpdateCellEdges(HexCell t)
    {
        var cell = _edgeMap[t.coord.a, t.coord.r, t.coord.c];
	    cell.boundary.MergeWith(t.boundary);

        // Edge map symmetry must be retained. That is -- if cell B has an edge
        // boundary with A, then A must also have a matching boundary with B.
        // Update neighbor cell boundaries to match.
        HecsCoord[] neighbors = t.coord.Neighbors();
        foreach (HecsCoord n in neighbors)
        {
            if (!CoordInMap(n)) continue;
            if (!cell.boundary.GetEdgeWith(t.coord, n)) continue;
            _edgeMap[n.a, n.r, n.c].boundary.SetEdgeWith(n, t.coord);
        }
    }

    private void UpdateEdgeMap(TileInformation tile)
    {
        UpdateCellEdges(tile.Cell);
    }

    private void UpdateMap()
    {
        if (_mapSource == null)
        {
            Debug.Log("Null map source.");
            return;
        }
        if (!_mapSource.IsMapReady())
        {
            // The map hasn't changed.
            return;
        }

        Debug.Log("Map available, performing update!");

        foreach (var tile in _grid) {
            if (tile == null) continue;
            if (tile.Model)
		        GameObject.Destroy(tile.Model);
            HecsCoord c = tile.Cell.coord;
            _grid[c.a, c.r, c.c] = null;
	    }

        List<TileInformation> tileList = _mapSource.FetchTileList();

        if (tileList == null)
        {
            Debug.Log("Null item list received.");
            return;
        }
        foreach (var t in tileList)
        {
            GameObject prefab = _assetSource.Load(t.AssetId);
            var tile = new Tile
            {
                Cell = t.Cell,
                AssetId = t.AssetId,
                Model = GameObject.Instantiate(prefab, t.Cell.Center(), Quaternion.identity),
			};
            UpdateEdgeMap(t);
            _grid[t.Cell.coord.a, t.Cell.coord.r, t.Cell.coord.c] = tile;
        }
    }
}
