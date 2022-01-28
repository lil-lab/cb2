using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class MturkUIController : MonoBehaviour
{
    public GameObject mturk_ui;
    public GameObject main_menu_ui;
    private const string SKIP_TO_TASK_PARAM = "skipToTask";
    private const string JOIN_QUEUE_TASK = "joinGameQueue";
    private const string LEADER_TUTORIAL_TASK = "leaderTutorial";
    private const string FOLLOWER_TUTORIAL_TASK = "followerTutorial";

    void Start()
    {
        // Only applies to WebGL contexts...
        if (Application.platform != RuntimePlatform.WebGLPlayer)
        {
            return;
        }
        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        if (urlParameters.ContainsKey(SKIP_TO_TASK_PARAM))
        {
            mturk_ui.SetActive(true);
            main_menu_ui.SetActive(false);
        }
    }

    public void JumpToMturkTask()
    {
        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        if (urlParameters.ContainsKey(SKIP_TO_TASK_PARAM))
        {
            string taskName = urlParameters[SKIP_TO_TASK_PARAM];
            switch(taskName)
            {
                case JOIN_QUEUE_TASK:
                    Debug.Log("[DEBUG] MTURK: Jumping to JoinGameQueue task.");
                    Network.NetworkManager.TaggedInstance().JoinGame();
                    break;
                case LEADER_TUTORIAL_TASK:
                    Network.NetworkManager.TaggedInstance().StartLeaderTutorial();
                    break;
                case FOLLOWER_TUTORIAL_TASK:
                    Network.NetworkManager.TaggedInstance().StartFollowerTutorial();
                    break;
            }
        }
    }
}
