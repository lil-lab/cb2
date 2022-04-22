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

        private Logger _logger;

        public NetworkMapSource()
        { 
            _logger = Logger.GetTrackedLogger("NetworkMapSource");
            if (_logger == null)
            {
                _logger = Logger.CreateTrackedLogger("NetworkRouter");
            }
        }

        public void ClearMapUpdate()
        {
            _logger.Info("ClearMapUpdate");
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
            _logger.Info("NetworkMapSource received map update.");
            
            // Log the number of cities, lakes, mountains and outposts.
            _logger.Info("Cities: " + mapInfo.metadata.num_cities);
            _logger.Info("Lakes: " + mapInfo.metadata.num_lakes);
            _logger.Info("Mountains: " + mapInfo.metadata.num_mountains);
            _logger.Info("Outposts: " + mapInfo.metadata.num_outposts);
            _logger.Info("Partitions: " + mapInfo.metadata.num_partitions);

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
            _logger.Debug("Retrieved list of tiles!");
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
                _logger.Error("RawMapUpdate() called before map update received.");
                return null;
            }
            return _lastMapReceived;
        }
    }
}  // namespace Network
