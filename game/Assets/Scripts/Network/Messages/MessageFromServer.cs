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
            ROOM_MANAGEMENT,
        }

        // These fields are always provided with any packet.
        public string TransmitTime;  // When the server transmitted this message in ISO 8601 format.

        // Message Type.
        public MessageType Type;

        // Only one of these is populated. Check the message type.
        public List<Action> Actions;
        public MapUpdate MapUpdate;
        public StateSync State;
        public RoomManagementResponse RoomManagementResponse;
    }
}  // namespace Network
