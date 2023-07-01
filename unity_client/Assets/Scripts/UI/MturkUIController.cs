using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class MturkUIController : MonoBehaviour
{
    public GameObject mturk_ui;
    public GameObject main_menu_ui;
    public GameObject queue_ui;
    private const string SKIP_TO_TASK_PARAM = "skipToTask";
    private const string ASSIGNMENT_ID_PARAM = "assignmentId";
    private const string JOIN_QUEUE_TASK = "joinGameQueue";
    private const string JOIN_FOLLOWER_QUEUE_TASK = "joinGameFollowerQueue";
    private const string LEADER_TUTORIAL_TASK = "leaderTutorial";
    private const string FOLLOWER_TUTORIAL_TASK = "followerTutorial";

    private const string CANCEL_QUEUE_BTN_TAG = "CANCEL_QUEUE_BTN";

    void Start()
    {
        // Only applies to WebGL contexts...
        if (Application.platform != RuntimePlatform.WebGLPlayer)
        {
            return;
        }
        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        if (urlParameters.ContainsKey(ASSIGNMENT_ID_PARAM))
        {
            mturk_ui.SetActive(true);
            main_menu_ui.SetActive(false);
        }
    }

    public void JumpToMturkTask()
    {
        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        string taskName = JOIN_QUEUE_TASK;
        if (urlParameters.ContainsKey(SKIP_TO_TASK_PARAM)) {
            taskName = urlParameters[SKIP_TO_TASK_PARAM];
        }
        switch(taskName)
        {
            case JOIN_QUEUE_TASK:
            {
                mturk_ui.SetActive(false);
                queue_ui.SetActive(true);
                Debug.Log("[DEBUG] MTURK: Jumping to JoinGameQueue task.");
                Network.NetworkManager.TaggedInstance().JoinGame();
                // Hide the cancel button to prevent players from doing the wrong task.
                GameObject cancelQueueBtn = GameObject.FindGameObjectWithTag(CANCEL_QUEUE_BTN_TAG);
                if (cancelQueueBtn != null)
                {
                    cancelQueueBtn.SetActive(false);
                }
                break;
            }
            case JOIN_FOLLOWER_QUEUE_TASK:
            {
                mturk_ui.SetActive(false);
                queue_ui.SetActive(true);
                Debug.Log("[DEBUG] MTURK: Jumping to JoinGameFollowerQueue task.");
                Network.NetworkManager.TaggedInstance().JoinAsFollower();
                // Hide the cancel button to prevent players from doing the wrong task.
                GameObject cancelQueueBtn = GameObject.FindGameObjectWithTag(CANCEL_QUEUE_BTN_TAG);
                if (cancelQueueBtn != null)
                {
                    cancelQueueBtn.SetActive(false);
                }
                break;
            }
            case LEADER_TUTORIAL_TASK:
                mturk_ui.SetActive(false);
                Network.NetworkManager.TaggedInstance().StartLeaderTutorial();
                break;
            case FOLLOWER_TUTORIAL_TASK:
                mturk_ui.SetActive(false);
                Network.NetworkManager.TaggedInstance().StartFollowerTutorial();
                break;
            default:
                Debug.LogError("[ERROR] MTURK: Unknown task name: " + taskName);
                break;
        }
    }
}
