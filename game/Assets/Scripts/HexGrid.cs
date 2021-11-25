using System.Collections;
using System.Collections.Generic;
using Network;
using UnityEngine;
using UnityEngine.SceneManagement;

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

    public bool EdgeBetween(HecsCoord a, HecsCoord b)
    {
        return _manager.EdgeBetween(a, b);
    }

    public HexCell Cell(HecsCoord a)
    {
        return _manager.Cell(a);
    }

    public float Height(HecsCoord a)
    {
        return _manager.Height(a);
    }

    void Start()
    {
        Scene activeScene = SceneManager.GetActiveScene();
        GameObject obj = GameObject.FindWithTag(Network.NetworkManager.TAG);
        HexGridManager.IMapSource mapSource = obj.GetComponent<Network.NetworkManager>().MapSource();
        Debug.Log("[DEBUG] Loading HexGrid.");
        _manager = new HexGridManager(mapSource, new UnityAssetSource());
        _manager.Start();
    }

    public void SetMap(HexGridManager.IMapSource map)
    {
        _manager.SetMap(map);
    }

    void Update()
    {
        _manager.DebugEdges(DebugEdges);
        _manager.Update();
    }
}