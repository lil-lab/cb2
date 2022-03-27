using System;

namespace Network
{
    public enum RoomRequestType
    {
        NONE = 0,
        STATS,
        JOIN,
        CANCEL,  // Cancel a previous JOIN.
        LEAVE,
    }

    [Serializable]
    public class RoomManagementRequest
    {
        public RoomRequestType type;
    }

}