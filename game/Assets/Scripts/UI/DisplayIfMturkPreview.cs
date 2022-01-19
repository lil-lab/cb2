using System.Collections;
using System.Collections.Generic;
using UnityEngine;

// Displays the GameObject if the game is run in a window with mturk URL
// parameters, and the assignment is in preview mode (not a real assignment).
public class DisplayIfMturkPreview : MonoBehaviour
{
    public static readonly string PreviewAssignmentId = "ASSIGNMENT_ID_NOT_AVAILABLE";
    void Start()
    {
        // Only applies to WebGL contexts...
        if (Application.platform != RuntimePlatform.WebGLPlayer)
        {
            gameObject.SetActive(false);
            return;
        }
        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        gameObject.SetActive(urlParameters.ContainsKey("assignmentId") && urlParameters["assignmentId"] == PreviewAssignmentId);
    }
}