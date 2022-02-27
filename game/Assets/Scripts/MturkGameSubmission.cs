using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System.Runtime.InteropServices;

public class MturkGameSubmission : MonoBehaviour
{
    [DllImport("__Internal")]
    private static extern void SubmitMturk(string game_data);

    // Check if this game is an Mturk task. If so, mark the task as submitted.
    void Start()
    {
        // Only applies to WebGL contexts...
        if (Application.platform != RuntimePlatform.WebGLPlayer) return;

        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        if (urlParameters.ContainsKey("assignmentId")) {
            Debug.Log("[DEBUG] MTURK: Marking task as submitted.");
            SubmitMturk("");
        }
    }
}
