using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using System;

public class SkipToScene : MonoBehaviour
{
    // Dictionary of secret keyboard combos to redirect to specific scenes from the main menu. See Start() for combos.
    private Dictionary<Tuple<KeyCode, KeyCode>, string> _sceneMap = new Dictionary<Tuple<KeyCode, KeyCode>, string>();
    private Dictionary<Tuple<KeyCode, KeyCode>, DateTime> _sceneKeysHeldTime = new Dictionary<Tuple<KeyCode, KeyCode>, DateTime>();

    void Start()
    {
        _sceneMap.Add(new Tuple<KeyCode, KeyCode>(KeyCode.X, KeyCode.R), "replay_scene");
        _sceneMap.Add(new Tuple<KeyCode, KeyCode>(KeyCode.X, KeyCode.M), "map_scene");
        foreach (var key in _sceneMap.Keys)
        {
            _sceneKeysHeldTime.Add(key, DateTime.MinValue);
        }
    }
    void Update()
    {
        // Wait until the NetworkManager is ready.
        if (Network.NetworkManager.TaggedInstance() == null)
        {
            return;
        }
        var urlParams = Network.NetworkManager.UrlParameters();
        if (urlParams.ContainsKey("map_viewer"))
        {
            SceneManager.LoadScene("map_viewer");
        }

        foreach (var sceneKey in _sceneMap.Keys)
        {
            if (Input.GetKey(sceneKey.Item1) && Input.GetKey(sceneKey.Item2))
            {
                if (_sceneKeysHeldTime[sceneKey] == DateTime.MinValue)
                {
                    _sceneKeysHeldTime[sceneKey] = DateTime.Now;
                }
                if (DateTime.Now - _sceneKeysHeldTime[sceneKey] > TimeSpan.FromSeconds(1))
                {
                    SceneManager.LoadScene(_sceneMap[sceneKey]);
                }
            } else {
                _sceneKeysHeldTime[sceneKey] = DateTime.MinValue;
            }
        }
    }
}
