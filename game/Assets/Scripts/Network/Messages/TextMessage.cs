using System;

namespace Network
{
    [Serializable]
    public class TextMessage
    {
        public Role Sender;
        public string Text;
    }
}