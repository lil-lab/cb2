using System.Collections;
using System.Collections.Generic;
using Network;
using UnityEngine;
using UnityEngine.SceneManagement;

public class HexGrid : MonoBehaviour
{
    public float Scale = 3.46f;
    public bool DebugEdges = false;

    public static string TAG = "HexGrid";

    private HexGridManager _manager;

    public static HexGrid TaggedInstance()
    {
        GameObject obj = GameObject.FindGameObjectWithTag(TAG);
        if (obj == null)
        {
            Debug.LogError("Could not find HexGrid with tag " + TAG);
            return null;
        }
        return obj.GetComponent<HexGrid>();
    }

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

    public Vector3 CenterPosition()
    {
        return _manager.CenterPosition();
    }

    public Vector3 Position(int i, int j)
    {
        return _manager.Position(i, j);
    }

    public (int, int) MapDimensions()
    {
        return _manager.MapDimensions();
    }

    void Start()
    {
        Scene activeScene = SceneManager.GetActiveScene();
        GameObject obj = GameObject.FindWithTag(Network.NetworkManager.TAG);
        Network.NetworkManager networkManager = obj.GetComponent<Network.NetworkManager>();
        IMapSource mapSource = networkManager.MapSource();
        if (networkManager.Role() == Network.Role.FOLLOWER)
        {
            // Subtract a 
            Scale += 0.04f;
        }
        Debug.Log("[DEBUG] Loading HexGrid.");
        _manager = new HexGridManager(mapSource, new UnityAssetSource());
        _manager.Start();
    }

    public void SetMap(IMapSource map)
    {
        _manager.SetMap(map);
    }

    void Update()
    {
        _manager.DebugEdges(DebugEdges);
        _manager.Update();
    }
}