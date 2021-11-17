﻿using System;
using System.Collections.Generic;

namespace Network
{

    [Serializable]
    public class MessageToServer
    {
        public enum MessageType
        {
            // Send list of player actions to the server.
            ACTIONS = 0,
            // Request the server send a state synch.
            STATE_SYNC_REQUEST,

            ROOM_MANAGEMENT,
        }

        // These fields are populated for every packet.
        public string TransmitTime;  // Transmission time of this message in ISO 8601 format.

        // Depending on the type, One of the following may be populated.
        public MessageType Type;

        public List<Action> Actions;
        public RoomManagementRequest RoomManagementRequest;
    }

}  // namespace Network
