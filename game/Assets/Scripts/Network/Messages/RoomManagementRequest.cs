namespace Network
{
    public enum RoomRequestType
    {
        NONE = 0,
        STATS,
        JOIN,
        LEAVE,
    }

    public class RoomManagementRequest
    {
        public RoomRequestType Type;
    }

}