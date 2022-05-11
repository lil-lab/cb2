using System;
using System.Collections.Generic;

namespace Network
{
    public enum Direction
    {
        NONE = 0,
        TO_SERVER,
        FROM_SERVER,
    }

    [Serializable]
    public class LogEntry
    {
        public Direction message_direction;
        public int player_id;
        public MessageFromServer message_from_server;
        public MessageToServer message_to_server;
    }

    [Serializable]
    public class GameInfo
    {
        public string start_time;
        public int game_id;
        public string game_name;
        public List<Role> roles;
        public List<int> ids; 
    }

    [Serializable]
    public class GameLog
    {
        public GameInfo game_info;
        public List<LogEntry> log_entries;
        // The server's config when the game was played.
        public Config server_config;
    }
}