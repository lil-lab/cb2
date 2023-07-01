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
        public string feedback_text = "";
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