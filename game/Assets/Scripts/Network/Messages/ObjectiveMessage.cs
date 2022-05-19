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
        public bool cancelled = false;

        public bool is_concluded()
        {
            return completed || cancelled;
        }
    }

    [Serializable]
    public class ObjectiveCompleteMessage
    {
        public string uuid = "";
    }
}