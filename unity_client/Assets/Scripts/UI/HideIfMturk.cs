using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HideIfMturk : MonoBehaviour
{
    void Start()
    {
        // Only applies to WebGL contexts...
        if (Application.platform != RuntimePlatform.WebGLPlayer)
        {
            gameObject.SetActive(true);
            return;
        }
        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        gameObject.SetActive(!urlParameters.ContainsKey("assignmentId"));
    }
}