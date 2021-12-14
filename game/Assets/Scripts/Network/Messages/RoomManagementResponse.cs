using System;


namespace Network
{
    public enum RoomResponseType
    {
        NONE = 0,
        STATS,
        JOIN_RESPONSE,
        LEAVE_NOTICE,
        ERROR
    }

    public enum Role
    {
        NONE = 0,
        FOLLOWER,
        LEADER
    }

    [Serializable]
    public class StatsResponse
    {
        public int NumberOfGames;
        public int PlayersInGame;
        public int PlayersWaiting;
    }

    public class JoinResponse
    {
        public bool Joined;  // Did the player join the room?

        // These are optionally populated depending on the value of Joined.
        public int PlaceInQueue;  // If Joined == false.
        public Role Role;  // If Joined == true.
    }

    [Serializable]
    public class LeaveRoomNotice
    {
        public string Reason;
    }

    [Serializable]
    public class RoomManagementResponse
    {
        public RoomResponseType Type;

        // Depending on the type above, these are optionally populated.
        public StatsResponse Stats;
        public JoinResponse JoinResponse;
        public LeaveRoomNotice LeaveNotice;
        public string Error;
    }
}
