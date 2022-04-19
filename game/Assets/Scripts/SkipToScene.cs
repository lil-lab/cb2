using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

public class SkipToScene : MonoBehaviour
{
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
    }
}
