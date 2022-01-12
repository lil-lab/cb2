using System;
using System.Collections.Generic;

namespace Network
{
    public enum TooltipType
    {
        NONE = 0,
        // The tooltip disappears after the user clicks on the "Ok" button on the tooltip text window or hits shift.
        UNTIL_DISMISSED,
        // The tooltip disappears once the player has sent a message.
        UNTIL_MESSAGE_SENT,
        UNTIL_CAMERA_TOGGLED,
        UNTIL_INDICATOR_REACHED,
        UNTIL_OBJECTIVES_COMPLETED,
        UNTIL_SET_COLLECTED,
    }

    [Serializable]
    public class Tooltip
    {
        public string HighlightedComponentTag;
        public string Text;

        // How to satisfy the tooltip.
        public TooltipType Type;
        public int KeyCode;
        public HecsCoord Location;
    }

    [Serializable]
    public class Indicator
    {
        public HecsCoord Location;
    }

    [Serializable]
    public class Instruction
    {
        public string Text;
    }

    [Serializable]
    public class TutorialStep
    {
        public Tooltip Tooltip;
        public Indicator Indicator;
        public Instruction Instruction;
    }

    [Serializable]
    public class TutorialComplete
    {
        public string TutorialName;
        public string CompletionDate;
    }

    public enum TutorialRequestType
    {
        NONE = 0,
        START_TUTORIAL,
        REQUEST_NEXT_STEP,
    }

    public enum TutorialResponseType
    {
        NONE = 0,
        STARTED,
        STEP,
        COMPLETED,
    }

    [Serializable]
    public class TutorialRequest
    {
        public static readonly string LEADER_TUTORIAL = "leader_tutorial";
        public static readonly string FOLLOWER_TUTORIAL = "follower_tutorial";
        public TutorialRequestType Type;
        public string TutorialName;
    }

    [Serializable]
    public class TutorialResponse
    {
        public TutorialResponseType Type;
        public string TutorialName;
        public TutorialStep Step;
        public TutorialComplete Complete;

        public Role Role()
        {
            if (TutorialName == "leader_tutorial")
            {
                return Network.Role.LEADER;
            }
            else if (TutorialName == "follower_tutorial")
            {
                return Network.Role.FOLLOWER;
            }
            return Network.Role.NONE;
        }
    }
}