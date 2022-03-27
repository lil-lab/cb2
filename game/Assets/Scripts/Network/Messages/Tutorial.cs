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
        public string highlighted_component_tag;
        public string text;

        // How to satisfy the tooltip.
        public TooltipType type;
        public int key_code;
        public HecsCoord location;
    }

    [Serializable]
    public class Indicator
    {
        public HecsCoord location;
    }

    [Serializable]
    public class Instruction
    {
        public string text;
    }

    [Serializable]
    public class TutorialStep
    {
        public Tooltip tooltip;
        public Indicator indicator;
        public Instruction instruction;
    }

    [Serializable]
    public class TutorialComplete
    {
        public string tutorial_name;
        public string completion_date;
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
        public TutorialRequestType type;
        public string tutorial_name;
    }

    [Serializable]
    public class TutorialResponse
    {
        public TutorialResponseType type;
        public string tutorial_name;
        public TutorialStep step;
        public TutorialComplete complete;

        public Role Role()
        {
            if (tutorial_name == "leader_tutorial")
            {
                return Network.Role.LEADER;
            }
            else if (tutorial_name == "follower_tutorial")
            {
                return Network.Role.FOLLOWER;
            }
            return Network.Role.NONE;
        }
    }
}