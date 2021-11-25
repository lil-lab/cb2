using System;
using System.Collections.Generic;
using UnityEngine;

namespace Network
{
    // Receives map updates from NetworkRouter and 
    public class NetworkMapSource : HexGridManager.IMapSource
    {
        private bool _networkMapReady = false;
        private int _rows = 0;
        private int _cols = 0;
        private List<HexGridManager.TileInformation> _map;

        public NetworkMapSource() { }

        public void ClearMapUpdate()
        {
            Debug.Log("ClearMapUpdate");
            _networkMapReady = false;
            _rows = 0;
            _cols = 0;
            _map = null;
        }
        public void ReceiveMapUpdate(Network.MapUpdate mapInfo)
        {
            _map = new List<HexGridManager.TileInformation>();
            _rows = mapInfo.Rows;
            _cols = mapInfo.Cols;

            foreach (Network.MapUpdate.Tile tile in mapInfo.Tiles)
            {
                _map.Add(new HexGridManager.TileInformation
                {
                    Cell = tile.Cell,
                    AssetId = (IAssetSource.AssetId)tile.AssetId,
                    RotationDegrees = tile.RotationDegrees,
                });
            }
            Debug.Log("NetworkMapSource received map update.");
            _networkMapReady = true;
        }

        // Retrieves the dimensions of the hexagon grid. Returns (rows, cols).
        public (int, int) GetMapDimensions()
        {
            return (_rows, _cols);
        }

        // List of tiles. Each tile represents one cell in the grid. Calling 
        // this causes IsMapReady() to return false until the next map update is
        // available.
        public List<HexGridManager.TileInformation> FetchTileList()
        {
            _networkMapReady = false;
            Debug.Log("[DEBUG] Retrieved list of tiles!");
            return _map;
        }

        // Returns true if a new map iteration is available.
        public bool IsMapReady()
        {
            return _networkMapReady;
        }
    }
}  // namespace Network
