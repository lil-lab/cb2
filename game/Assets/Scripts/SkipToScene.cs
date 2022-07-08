using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using System;

public class SkipToScene : MonoBehaviour
{
    enum ActionType
    {
        NONE = 0,
        SKIP_TO_SCENE,
        JOIN_FOLLOWER_QUEUE,
    }
    struct Action
    {
        public ActionType type;
        public string sceneName;  // If type == SKIP_TO_SCENE.
    }

    // Dictionary of secret keyboard combos to redirect to specific scenes from the main menu. See Start() for combos.
    private Dictionary<Tuple<KeyCode, KeyCode>, Action> _sceneMap = new Dictionary<Tuple<KeyCode, KeyCode>, Action>();
    private Dictionary<Tuple<KeyCode, KeyCode>, DateTime> _sceneKeysHeldTime = new Dictionary<Tuple<KeyCode, KeyCode>, DateTime>();

    void Start()
    {
        _sceneMap.Add(new Tuple<KeyCode, KeyCode>(KeyCode.X, KeyCode.R), SceneTransition("replay_scene"));
        _sceneMap.Add(new Tuple<KeyCode, KeyCode>(KeyCode.X, KeyCode.M), SceneTransition("map_viewer"));
        _sceneMap.Add(new Tuple<KeyCode, KeyCode>(KeyCode.X, KeyCode.F), JoinFollowerQueue());
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

        if (urlParams.ContainsKey("replay_game"))
        {
            SceneManager.LoadScene("replay_scene");
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
                    Action action = _sceneMap[sceneKey];
                    if (action.type == ActionType.SKIP_TO_SCENE)
                    {
                        SceneManager.LoadScene(action.sceneName);
                    }
                    else if (action.type == ActionType.JOIN_FOLLOWER_QUEUE)
                    {
                        Network.NetworkManager.TaggedInstance().JoinAsFollower();
                    }
                    _sceneKeysHeldTime[sceneKey] = DateTime.MinValue;
                }
            } else {
                _sceneKeysHeldTime[sceneKey] = DateTime.MinValue;
            }
        }
    }

    Action SceneTransition(string name)
    {
        Action action = new Action();
        action.type = ActionType.SKIP_TO_SCENE;
        action.sceneName = name;
        return action;
    }

    Action JoinFollowerQueue()
    {
        Action action = new Action();
        action.type = ActionType.JOIN_FOLLOWER_QUEUE;
        return action;
    }
}
