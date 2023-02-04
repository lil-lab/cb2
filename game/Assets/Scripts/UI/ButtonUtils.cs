using UnityEngine;
using UnityEngine.UI;

public class ButtonUtils
{
    public static string Text(Network.ButtonCode action)
    {
        switch (action)
        {
            case Network.ButtonCode.JOIN_QUEUE:
                return "Join Queue";
            case Network.ButtonCode.LEAVE_QUEUE:
                return "Leave Queue";
            case Network.ButtonCode.JOIN_FOLLOWER_QUEUE:
                return "Join Follower Queue";
            case Network.ButtonCode.JOIN_LEADER_QUEUE:
                return "Join Leader Queue";
            case Network.ButtonCode.START_LEADER_TUTORIAL:
                return "Start Leader Tutorial";
            case Network.ButtonCode.START_FOLLOWER_TUTORIAL:
                return "Start Follower Tutorial";
            default:
                return "Unknown";
        }
    }

    public static void HandleAction(Network.ButtonCode action)
    {
        Logger logger = Logger.GetOrCreateTrackedLogger("ButtonUtils");
        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();
        if (networkManager == null)
        {
            logger.Warn("NetworkManager not ready.");
            return;
        }

        switch (action)
        {
            case Network.ButtonCode.NONE:
                break;
            case Network.ButtonCode.JOIN_QUEUE:
                networkManager.JoinGame();
                MenuTransitionHandler.ShowWaitQueue();
                break;
            case Network.ButtonCode.LEAVE_QUEUE:
                networkManager.CancelGameQueue();
                MenuTransitionHandler.ShowMainMenu();
                break;
            case Network.ButtonCode.JOIN_FOLLOWER_QUEUE:
                networkManager.JoinAsFollower();
                MenuTransitionHandler.ShowWaitQueue();
                break;
            case Network.ButtonCode.JOIN_LEADER_QUEUE:
                networkManager.JoinAsLeader();
                MenuTransitionHandler.ShowWaitQueue();
                break;
            case Network.ButtonCode.START_LEADER_TUTORIAL:
                networkManager.StartLeaderTutorial();
                break;
            case Network.ButtonCode.START_FOLLOWER_TUTORIAL:
                networkManager.StartFollowerTutorial();
                break;
            default:
                logger.Warn("Unknown action: " + action);
                break;
        }
    }
}