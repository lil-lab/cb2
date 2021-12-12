using System;

namespace Network
{
    [Serializable]
    public class ObjectiveMessage
    {
        public Role Sender;
        public string Text;
        public string Uuid = "";
        public bool Completed = false;
    }

    [Serializable]
    public class ObjectiveCompleteMessage
    {
        public string Uuid = "";
    }
}