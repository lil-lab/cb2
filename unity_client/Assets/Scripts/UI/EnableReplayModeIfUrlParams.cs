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
}
