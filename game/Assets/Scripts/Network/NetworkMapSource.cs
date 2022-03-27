using System;
using System.Collections.Generic;
using UnityEngine;

namespace Network
{
    // Receives map updates from NetworkRouter and 
    public class NetworkMapSource : IMapSource
    {
        private bool _networkMapReady = false;
        private int _rows = 0;
        private int _cols = 0;
        private List<HexGridManager.TileInformation> _map;
        private Network.MapUpdate _lastMapReceived;

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
            _rows = mapInfo.rows;
            _cols = mapInfo.cols;

            foreach (Network.MapUpdate.Tile tile in mapInfo.tiles)
            {
                _map.Add(new HexGridManager.TileInformation
                {
                    Cell = tile.cell,
                    AssetId = (IAssetSource.AssetId)tile.asset_id,
                    RotationDegrees = tile.rotation_degrees,
                });
            }
            Debug.Log("NetworkMapSource received map update.");
            _networkMapReady = true;
            _lastMapReceived = mapInfo;
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

        // Returns the raw map update datastructure. Used for bug reporting.
        public Network.MapUpdate RawMapUpdate()
        {
            if (_lastMapReceived == null)
            {
                Debug.LogError("RawMapUpdate() called before map update received.");
                return null;
            }
            return _lastMapReceived;
        }
    }
}  // namespace Network
