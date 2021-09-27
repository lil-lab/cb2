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
public class HexGridManager : MonoBehaviour
{
    // Describes a cell in a hexagonal grid, including the edge occupancy.
    public class Cell
    {
        public HecsCoord coord;
        public HexBoundary boundary;
    }

    // Metadata describing an item held in the game map.
    public class ItemInformation
    {
        public int assetId;  // For prefab retrieval.
        public HecsCoord coord;
        public int rotationDegrees;  // Multiple of 60 for grid alignment.
        public int width, height;  // Dimens in hexagonal cells.
        public List<Cell> edgeMap;  // Edge occupancy. HECS indices.
    }

    public class Item
    {
        public ItemInformation info;
        public GameObject prefab;
    }

    // Interface for loading assets.
    public interface IAssetSource
    {
        Item Load(int assetId);
    }

    // Interface for retrieving map updates.
    public interface IMapSource
    {
        // Retrieves the dimensions of the hexagon grid.
        (int, int) GetMapDimensions();

        // List of grid assets. Each item represents one or more cells in the grid.
        List<ItemInformation> GetItemList();

        // Returns an integer. Increments each time any change is made to the map.
        // If the iteration remains unchanged, no re-rendering needs to be done.
        // Technically there's a race condition between this and GetGrid.
        // TODO(sharf): update this interface to be atomic with GetGrid().
        // Worst case with this race, too much rendering is done, or an update
        // comes a bit late.
        int GetMapIteration();
    }

    private IMapSource _mapSource;
    private IAssetSource _assetSource;

    // Used to determine if player can walk through an edge.
    private HexBoundary[,,] _edgeMap;

    // A list of all the assets currently placed in the map. If an asset occupies multiple cells, then it will appear at the "root" cell.
    private Item[,,] _grid;

    // Used to check if the map needs to be re-loaded.
    private int _lastMapIteration = 0;

    public HexGridManager(IMapSource mapSource, IAssetSource assetSource)
    {
        _mapSource = mapSource;
        _assetSource = assetSource;
    }

    // Start is called before the first frame update
    void Start()
    {
        (int rows, int cols) = _mapSource.GetMapDimensions();
        _grid = new Item[2, rows / 2, cols];
        _edgeMap = new HexBoundary[2, rows / 2, cols];

        // Pre-initialize the edge map to be all-empty.
        for (int r = 0; r < rows; r++)
        {
            for (int c = 0; c < cols; c++)
            {
                int hecsA = r % 2;
                int hecsR = r / 2;
                int hecsC = c;
                _edgeMap[hecsA, hecsR, hecsC] = new HexBoundary();
            }
        }
    }

    // Updates the edge boundary map for a single cell.
    private void UpdateCellEdges(Cell c)
    {
        _edgeMap[c.coord.a, c.coord.r, c.coord.c].MergeWith(c.boundary);

        // Edge map symmetry must be retained. That is -- if cell B has an edge
        // boundary with A, then A must also have a matching boundary with B.
        // Update neighbor cell boundaries to match.
        HecsCoord[] neighbors = c.coord.Neighbors();
        foreach (HecsCoord n in neighbors)
        {
            _edgeMap[n.a, n.r, n.c].SetEdgeWith(n, c.coord);
        }
    }

    // Updates the edge boundary map to add an item.
    private void UpdateEdgeMap(ItemInformation item)
    {
        foreach(Cell c in item.edgeMap)
        {
            UpdateCellEdges(c);
        }
    }

    private void UpdateMap()
    {
        if (_mapSource == null)
        {
            Debug.Log("Null map source.");
            return;
        }
        int iteration = _mapSource.GetMapIteration();
        if (iteration == _lastMapIteration)
        {
            // The map hasn't changed.
            return;
        }

        List<ItemInformation> itemList = _mapSource.GetItemList();

        if (itemList == null)
        {
            Debug.Log("Null item list received.");
            return;
        }
        foreach (var item in itemList)
        {
            _grid[item.coord.a, item.coord.r, item.coord.c] = _assetSource.Load(item.assetId);
            UpdateEdgeMap(item);
        }
        _lastMapIteration = iteration;
    }

    // Update is called once per frame
    void Update()
    {
        UpdateMap();
    }
}
