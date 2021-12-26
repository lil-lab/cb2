using System;
using UnityEngine;
using System.Collections.Generic;

// Interface for retrieving map updates.
public interface IMapSource
{
    // Retrieves the dimensions of the hexagon grid. Returns (rows, cols).
    (int, int) GetMapDimensions();

    // List of tiles. Each tile represents one cell in the grid. Calling 
    // this causes IsMapReady() to return false until the next map update is
    // available.
    List<HexGridManager.TileInformation> FetchTileList();

    // Returns true if a new map iteration is available.
    bool IsMapReady();

    // Returns the raw network map update datastructure. Used for bug reporting.
    public Network.MapUpdate RawMapUpdate();
}
