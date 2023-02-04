using System;
using System.Collections.Generic;

namespace Network
{

public enum ButtonCode
{
    NONE = 0,
    // Queue.
    JOIN_QUEUE = 1,
    LEAVE_QUEUE = 2,
    JOIN_FOLLOWER_QUEUE = 3,
    JOIN_LEADER_QUEUE = 4,
    // Start tutorial.
    START_LEADER_TUTORIAL = 5,
    START_FOLLOWER_TUTORIAL = 6,
}

public class ButtonDescriptor
{
    public ButtonCode code;
    public string text;
    public string tooltip;
}

[Serializable]
public class MenuOptions
{
    public List<ButtonDescriptor> buttons;
    public string bulletin_message;
}

}  // namespace Network