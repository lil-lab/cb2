using System;
using System.Collections.Generic;

namespace Network
{

    [Serializable]
    public class MessageToServer
    {
        public enum MessageType
        {
            ACTIONS = 0,
        }

        // These fields are populated for every packet.
        public string TransmitTime;  // Transmission time of this message in ISO 8601 format.

        // Depending on the type, only one of the following is populated.
        public MessageType Type;

        public List<Action> Actions;

    }

}  // namespace Network
