using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HexGrid : MonoBehaviour
{
    public float Scale = 1;

    public static string TAG = "HexGrid";

    private HexGridManager _manager;

    private FixedMapSource.Tile[,] GetTileMap()
    {
        FixedMapSource.Tile[,] mapInfo = new FixedMapSource.Tile[20, 20];
        for (int i = 0; i < 20; ++i)
        {
            for (int j = 0; j < 20; ++j)
            {
                mapInfo[i,j] = FixedMapSource.GroundTile();
            }
        }
        return mapInfo;
    }

    void Awake()
    {
        gameObject.tag = TAG;
    }

    void Start()
    {
        FixedMapSource.Tile[,] mapInfo = GetTileMap();
        _manager = new HexGridManager(new FixedMapSource(mapInfo), new UnityAssetSource());
        _manager.Start();
    }

    void Update()
    {
        _manager.Update();
    }
}
