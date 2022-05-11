using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using System;

public class EnableReplayModeIfUrlParams : MonoBehaviour
{
    public static readonly string REPLAY_MODE_PARAM = "replayMode";

    private DateTime _start = DateTime.MinValue;

    void Start()
    {
        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        if (urlParameters.ContainsKey(REPLAY_MODE_PARAM))
        {
            if (urlParameters[REPLAY_MODE_PARAM] == "true")
            {
                SceneManager.LoadScene("replay_scene");
            }
        }
    }

    void Update()
    {
        if (Input.GetKey(KeyCode.X) && Input.GetKey(KeyCode.R))
        {
            if (_start == DateTime.MinValue)
            {
                _start = DateTime.Now;
            }
            if (DateTime.Now - _start > TimeSpan.FromSeconds(1))
            {
                SceneManager.LoadScene("replay_scene");
            }
        } else {
            _start = DateTime.MinValue;
        }

    }
}
