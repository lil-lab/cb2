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
            _logger = Logger.GetOrCreateTrackedLogger("NetworkMapSource");
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
            _logger.Info("ReceiveMapUpdate()");
            _map = new List<HexGridManager.TileInformation>();
            _rows = mapInfo.rows;
            _cols = mapInfo.cols;

            foreach (Network.Tile tile in mapInfo.tiles)
            {
                _map.Add(new HexGridManager.TileInformation
                {
                    Cell = tile.cell,
                    AssetId = (IAssetSource.AssetId)tile.asset_id,
                    RotationDegrees = tile.rotation_degrees,
                });
            }
            _logger.Info("NetworkMapSource received map update.");
            
            if (mapInfo.metadata != null)
            {
                // Log the number of cities, lakes, mountains and outposts.
                _logger.Info("Cities: " + mapInfo.metadata.cities.Count);
                _logger.Info("Lakes: " + mapInfo.metadata.lakes.Count);
                _logger.Info("Mountains: " + mapInfo.metadata.mountains.Count);
                _logger.Info("Outposts: " + mapInfo.metadata.outposts.Count);
                _logger.Info("Partitions: " + mapInfo.metadata.num_partitions);

                _logger.Info("Cities: ");
                foreach (Network.City city in mapInfo.metadata.cities)
                {
                    _logger.Info("r: " + city.r + ", c: " + city.c + ", size: " + city.size);
                }

                _logger.Info("Lakes: ");
                foreach (Network.Lake lake in mapInfo.metadata.lakes)
                {
                    _logger.Info("r: " + lake.r + ", c: " + lake.c + ", size: " + lake.size + ", type: " + lake.type.ToString());
                }

                _logger.Info("Mountains: ");
                foreach (Network.Mountain mountain in mapInfo.metadata.mountains)
                {
                    _logger.Info("r: " + mountain.r + ", c: " + mountain.c + ", type: " + mountain.type.ToString() + ", snowy: " + mountain.snowy);
                }

                _logger.Info("Outposts: ");
                foreach (Network.Outpost outpost in mapInfo.metadata.outposts)
                {
                    _logger.Info("r: " + outpost.r + ", c: " + outpost.c + ", connection_a: " + outpost.connection_a.ToString() + ", connection_b: " + outpost.connection_b.ToString());
                }

                // Print the size of each partition on one line:
                _logger.Info("Partition sizes: " + string.Join(", ", mapInfo.metadata.partition_sizes));
            }

            // If the map has fog, set the fog distance.
            if ((mapInfo.fog_start.HasValue) && (mapInfo.fog_end.HasValue))
            {
                if (mapInfo.fog_start.Value < 0)
                {
                    RenderSettings.fog = false;
                    _logger.Error("Fog start distance is negative: " + mapInfo.fog_start.Value);
                } else {
                    RenderSettings.fog = true;
                    RenderSettings.fogStartDistance = mapInfo.fog_start.Value;
                    RenderSettings.fogEndDistance = mapInfo.fog_end.Value;
                    _logger.Info("Fog enabled. Start: " + mapInfo.fog_start.Value + ", End: " + mapInfo.fog_end.Value);
                }
            } else {
                // No fog info provided. Check server config.
                if (!ConfigureSystemFog())
                {
                    _logger.Warn("Fog info not provided and server config not found. Fog disabled.");
                    RenderSettings.fog = false;
                }
            }

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

        private bool ConfigureSystemFog()
        {
            Logger logger = Logger.GetOrCreateTrackedLogger("FogUtils");
            Network.Config cfg = global::Network.NetworkManager.TaggedInstance().ServerConfig();
            if (cfg == null) return false;
            if (cfg.fog_start < 0)
            {
                RenderSettings.fog = false;
                logger.Info("Fog disabled");
                return true;
            }
            else
            {
                RenderSettings.fog = true;
                logger.Info("Fog enabled");
            }
            RenderSettings.fogStartDistance = cfg.fog_start;
            RenderSettings.fogEndDistance = cfg.fog_end;
            logger.Info("Fog initialized with start: " + cfg.fog_start + " and end: " + cfg.fog_end);
            return true;
        }
    }
}  // namespace Network
