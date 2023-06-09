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
        THROW_EXCEPTION,  // For debugging client exception upload.
    }
    struct Action
    {
        public ActionType type;
        public string sceneName;  // If type == SKIP_TO_SCENE.
    }

    // Dictionary of secret keyboard combos to redirect to specific scenes from the main menu. See Start() for combos.
    private Dictionary<Tuple<KeyCode, KeyCode>, Action> _sceneMap = new Dictionary<Tuple<KeyCode, KeyCode>, Action>();
    private Dictionary<Tuple<KeyCode, KeyCode>, DateTime> _sceneKeysHeldTime = new Dictionary<Tuple<KeyCode, KeyCode>, DateTime>();
    private Dictionary<Tuple<KeyCode, KeyCode>, bool> _sceneKeysTriggered = new Dictionary<Tuple<KeyCode, KeyCode>, bool>();

    bool _networkManagerInited = false;

    void Start()
    {
        _sceneMap.Add(new Tuple<KeyCode, KeyCode>(KeyCode.X, KeyCode.R), SceneTransition("replay_scene"));
        _sceneMap.Add(new Tuple<KeyCode, KeyCode>(KeyCode.X, KeyCode.M), SceneTransition("map_viewer"));
        _sceneMap.Add(new Tuple<KeyCode, KeyCode>(KeyCode.X, KeyCode.F), JoinFollowerQueue());
        _sceneMap.Add(new Tuple<KeyCode, KeyCode>(KeyCode.X, KeyCode.Backslash), ThrowException());
        foreach (var key in _sceneMap.Keys)
        {
            _sceneKeysHeldTime.Add(key, DateTime.MinValue);
            _sceneKeysTriggered.Add(key, false);
        }
    }

    void NetworkManagerStartup() {
        if (_networkManagerInited) return;
        var urlParams = Network.NetworkManager.UrlParameters();
        if (urlParams.ContainsKey("map_viewer"))
        {
            SceneManager.LoadScene("map_viewer");
        }

        if (urlParams.ContainsKey("replay_game"))
        {
            SceneManager.LoadScene("replay_scene");
        }

        if (urlParams.ContainsKey("auto"))
        {
            if (urlParams["auto"] == "join_follower_queue")
            {
                Network.NetworkManager.TaggedInstance().JoinAsFollower();
            }
            else if (urlParams["auto"] == "join_game_queue")
            {
                Network.NetworkManager.TaggedInstance().JoinGame();
            }
        }
        _networkManagerInited = true;
    }

    void Update()
    {
        // Wait until the NetworkManager is ready.
        if (!_networkManagerInited && (Network.NetworkManager.TaggedInstance() != null))
        {
            NetworkManagerStartup();
        }

        foreach (var sceneKey in _sceneMap.Keys)
        {
            if (Input.GetKey(sceneKey.Item1) && Input.GetKey(sceneKey.Item2))
            {
                if (_sceneKeysHeldTime[sceneKey] == DateTime.MinValue)
                {
                    _sceneKeysHeldTime[sceneKey] = DateTime.UtcNow;
                }
                if ((DateTime.UtcNow - _sceneKeysHeldTime[sceneKey] > TimeSpan.FromSeconds(1)) && (!_sceneKeysTriggered[sceneKey]))
                {
                    // Save the event so it doesn't trigger again. We do this
                    // here first, as the throw exception action will cause the
                    // function to exit early.
                    _sceneKeysTriggered[sceneKey] = true;
                    Action action = _sceneMap[sceneKey];
                    if (action.type == ActionType.SKIP_TO_SCENE)
                    {
                        SceneManager.LoadScene(action.sceneName);
                    }
                    else if (action.type == ActionType.JOIN_FOLLOWER_QUEUE)
                    {
                        Network.NetworkManager.TaggedInstance().JoinAsFollower();
                    } else if (action.type == ActionType.THROW_EXCEPTION) {
                        throw new System.Exception("This is a test exception triggered from SkipToScene in main menu.");
                    } else {
                        Debug.LogError("Unknown SkipToScene action type: " + action.type);
                    }
                }
            } else {
                _sceneKeysHeldTime[sceneKey] = DateTime.MinValue;
                _sceneKeysTriggered[sceneKey] = false;
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

    Action ThrowException()
    {
        Action action = new Action();
        action.type = ActionType.THROW_EXCEPTION;
        return action;
    }
}
