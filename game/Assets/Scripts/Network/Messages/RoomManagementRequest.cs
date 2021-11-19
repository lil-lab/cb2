using System;

namespace Network
{
    public enum RoomRequestType
    {
        NONE = 0,
        STATS,
        JOIN,
        LEAVE,
    }

    [Serializable]
    public class RoomManagementRequest
    {
        public RoomRequestType Type;
    }

}