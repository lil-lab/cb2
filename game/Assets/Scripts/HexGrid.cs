using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HexGrid : MonoBehaviour
{
    public float Scale = 3.49f;
    public bool DebugEdges = false;

    public static string TAG = "HexGrid";

    private HexGridManager _manager;

    void Awake()
    {
        gameObject.tag = TAG;
    }

    public bool EdgeBetween(HecsCoord a, HecsCoord b) {
        return _manager.EdgeBetween(a, b);
    }

    void Start()
    {
        _manager = new HexGridManager(new FixedMapSource(), new UnityAssetSource());
        _manager.Start();
    }

    void Update()
    {
        _manager.DebugEdges(DebugEdges);
        _manager.Update();
    }
}
