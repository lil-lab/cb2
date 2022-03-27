using System;

namespace Network
{
    [Serializable]
    public class ObjectiveMessage
    {
        public Role sender;
        public string text;
        public string uuid = "";
        public bool completed = false;
    }

    [Serializable]
    public class ObjectiveCompleteMessage
    {
        public string uuid = "";
    }
}