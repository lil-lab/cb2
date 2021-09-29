using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HexGrid : MonoBehaviour
{
    public float Scale = 1;

    public static string TAG = "HexGrid";

    private HexGridManager _manager;

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
