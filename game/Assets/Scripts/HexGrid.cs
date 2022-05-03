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

    private Logger _logger;

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

    Util.Status InitializeManager()
    {
        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();
        IMapSource mapSource = networkManager.MapSource();
        if (networkManager.Role() == Network.Role.FOLLOWER)
        {
            // Increase the gap between cells if we're a follower to reveal the grid.
            Scale += 0.04f;
        }
        Debug.Log("[DEBUG] Loading HexGrid.");
        _manager = new HexGridManager();
        _manager.Start(mapSource, new UnityAssetSource());
        return Util.Status.OkStatus();
    }

    void Start()
    {
        _logger = Logger.GetOrCreateTrackedLogger("HexGrid");
        InitializeManager();
    }

    public void SetMap(IMapSource map)
    {
        _manager.SetMap(map);
    }

    public void OnEnable()
    {
        Debug.Log("HexGrid: OnEnable()");
        if (_manager == null)
        {
            Debug.Log("HexGrid: Start()");
            Start();
            _logger.Info("HexGridManager re-initialized.");
        }
    }

    void Update()
    {
        _manager.DebugEdges(DebugEdges);
        _manager.Update();
    }
}