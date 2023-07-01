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
        MAP_SAMPLE,
        JOIN_FOLLOWER_ONLY,
        JOIN_LEADER_ONLY,
    }

    [Serializable]
    public class RoomManagementRequest
    {
        public RoomRequestType type;
    }

}