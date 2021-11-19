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
        HexGridManager.IMapSource mapSource = null;
        if (activeScene.name == "menu_scene")
        {
            mapSource = new FixedMapSource();
        }
        else if (activeScene.name == "game_scene")
        {
            GameObject obj = GameObject.FindWithTag(Network.NetworkManager.TAG);
            mapSource = obj.GetComponent<Network.NetworkManager>().MapSource();
        }
        else
        {
            Debug.LogError("Unknown scene: " + activeScene.name);
        }
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