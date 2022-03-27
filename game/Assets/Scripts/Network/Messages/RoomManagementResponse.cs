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
        public int number_of_games;
        public int players_in_game;
        public int players_waiting;
    }

    public class JoinResponse
    {
        public bool joined;  // Did the player join the room?

        // These are optionally populated depending on the value of Joined.
        public int place_in_queue;  // If Joined == false.
        public Role role;  // If Joined == true.
    }

    [Serializable]
    public class LeaveRoomNotice
    {
        public string reason;
    }

    [Serializable]
    public class RoomManagementResponse
    {
        public RoomResponseType type;

        // Depending on the type above, these are optionally populated.
        public StatsResponse stats;
        public JoinResponse join_response;
        public LeaveRoomNotice leave_notice;
        public string error;
    }
}
