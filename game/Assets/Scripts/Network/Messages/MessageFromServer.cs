using System;
using System.Collections.Generic;

namespace Network
{

    [Serializable]
    public class MessageFromServer
    {
	    public enum MessageType
	    {
			ACTIONS = 0,
			MAP_UPDATE,
			STATE_SYNC,
	    }

        // These fields are always provided with any packet.
        public DateTime TransmitTime;  // When the server transmitted this message.

        // Message Type.
        public MessageType Type;

        // Only one of these is populated. Check the message type.
        public List<Action> Actions;
        public MapUpdate MapUpdate;
        public StateSync State;
    }
}  // namespace Network
