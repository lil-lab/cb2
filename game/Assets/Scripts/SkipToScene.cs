using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using System;

public class SkipToScene : MonoBehaviour
{
    private DateTime _mapKeyHeldTime = DateTime.MinValue;
    void Start()
    {
        // SceneManager.LoadScene("map_viewer");
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

        // If the X & M buttons are held down for 3 seconds, skip to the map viewer.
        if (Input.GetKey(KeyCode.M) && Input.GetKey(KeyCode.X))
        {
            if (_mapKeyHeldTime == DateTime.MinValue)
            {
                _mapKeyHeldTime = DateTime.Now;
            }
            else if (DateTime.Now - _mapKeyHeldTime > TimeSpan.FromSeconds(3))
            {
                SceneManager.LoadScene("map_viewer");
            }
        }
        else
        {
            _mapKeyHeldTime = DateTime.MinValue;
        }
    }
}
