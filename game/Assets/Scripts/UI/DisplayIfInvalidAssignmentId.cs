using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class DisplayIfInvalidAssignmentId : MonoBehaviour
{
    // Start is called before the first frame update
    void Start()
    {
        // Only applies to WebGL contexts...
        if (Application.platform != RuntimePlatform.WebGLPlayer)
        {
            gameObject.SetActive(false);
            return;
        }
        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        gameObject.SetActive(!urlParameters.ContainsKey("assignmentId"));
    }
}
