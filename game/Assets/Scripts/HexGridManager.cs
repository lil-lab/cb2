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
        public IAssetSource.AssetId AssetId;
        public HexCell Cell;
        public int RotationDegrees;  // Multiple of 60 for grid alignment.
    }

    public class Tile
    {
        public IAssetSource.AssetId AssetId;
        public HexCell Cell;
        public int RotationDegrees;  // Multiple of 60 for grid alignment.
        public GameObject Model;
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

    // Map information.
    private Tile[,,] _grid;

    // If true, draws debug lines showing boundaries in the edge map.
    public bool _debugEdges = false;

    public HexGridManager(IMapSource mapSource, IAssetSource assetSource)
    {
        _mapSource = mapSource;
        _assetSource = assetSource;
    }

    public void SetMap(IMapSource mapSource)
    {
        _mapSource = mapSource;
    }

    public void InitializeGrid()
    {
        (int rows, int cols) = _mapSource.GetMapDimensions();
        Debug.Log("rows: " + rows + ", cols:" + cols);
        _grid = new Tile[2, rows / 2, cols];

        // Pre-initialize the edge map to be all-empty.
        for (int r = 0; r < rows; r++)
        {
            for (int c = 0; c < cols; c++)
            {
                int hecsA = r % 2;
                int hecsR = r / 2;
                int hecsC = c;

                _grid[hecsA, hecsR, hecsC] = new Tile();
                _grid[hecsA, hecsR, hecsC].Cell = new HexCell(
                    new HecsCoord(hecsA, hecsR, hecsC), new HexBoundary());
            }
        }
    }

    public void Start()
    {
        InitializeGrid();
    }

    public void Update()
    {
        UpdateMap();
        if (_debugEdges)
        {
            foreach (Tile t in _grid)
            {
                HexCell c = t.Cell;
                if (c.boundary.Serialize() == 0) continue;
                var vertices = c.Vertices();
                (int row, int col) = c.coord.ToOffsetCoordinates();
                Vector3 checkerboardOffset = (row % 2 == 0 && col % 2 == 0) ? new Vector3(0, 1.0f, 0.0f) : new Vector3(0, 0, 0);
                for (int i = 0; i < 6; ++i)
                {
                    vertices[i] += checkerboardOffset;
                }
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
                    Debug.DrawLine(vertices[2], vertices[3], Color.cyan, 2.0f, true);
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
        return _grid[a.a, a.r, a.c].Cell.boundary.GetEdgeWith(a, b);
    }

    public bool in_grid(HecsCoord a)
    {
        if (!(0 <= a.a && a.a < _grid.GetLength(0)))
            return false;
        if (!(0 <= a.r && a.r < _grid.GetLength(1)))
            return false;
        if (!(0 <= a.c && a.c < _grid.GetLength(2)))
            return false;
        return true;
    }

    public float Height(HecsCoord a)
    {
        if (!in_grid(a))
        {
            return 0;
        }
        return _grid[a.a, a.r, a.c].Cell.height;
    }

    public void DebugEdges(bool val)
    {
        _debugEdges = val;
    }

    public HexCell Cell(HecsCoord a)
    {
        return _grid[a.a, a.r, a.c].Cell;
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
        var cell = _grid[t.coord.a, t.coord.r, t.coord.c].Cell;

        // Edge map symmetry must be retained. That is -- if cell B has an edge
        // boundary with A, then A must also have a matching boundary with B.
        // Update neighbor cell boundaries to match. Remove neighboring boundaries if
        // the edge is unblocked in the new cell.
        HecsCoord[] neighbors = t.coord.Neighbors();
        foreach (HecsCoord n in neighbors)
        {
            if (!CoordInMap(n)) continue;
            if (!cell.boundary.GetEdgeWith(t.coord, n)) continue;

            _grid[n.a, n.r, n.c].Cell.boundary.SetEdgeWith(n, t.coord);
        }
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

        foreach (var tile in _grid)
        {
            if (tile == null) continue;
            if (tile.Model)
                GameObject.Destroy(tile.Model);
            HecsCoord c = tile.Cell.coord;
            _grid[c.a, c.r, c.c] = null;
        }

        InitializeGrid();

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
                RotationDegrees = t.RotationDegrees,
                Model = GameObject.Instantiate(prefab, t.Cell.Center(), Quaternion.AngleAxis(t.RotationDegrees, new Vector3(0, 1, 0))),
            };
            _grid[t.Cell.coord.a, t.Cell.coord.r, t.Cell.coord.c] = tile;
        }
        foreach (Tile t in _grid)
        {
            UpdateCellEdges(t.Cell);
        }

    }
}
