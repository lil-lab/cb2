using System;
using System.Collections.Generic;

namespace Network
{
    public enum ReplayCommand
    {
        NONE = 0,
        PLAY,
        PAUSE,
        PREVIOUS,
        NEXT,
        RESET,
        REPLAY_SPEED,
    }

    [Serializable]
    public class ReplayInfo
    {
        public int game_id;
        public string start_time;
        public bool paused;
        public int tick;
        public int total_ticks;
        public int turn;
        public int total_turns;
        // When the message was sent in the original game.
        public string transmit_time;
        public float percent_complete;
    }

    public enum ReplayRequestType
    {
        NONE = 0,
        START_REPLAY,
        REPLAY_COMMAND,
    }

    [Serializable]
    public class ReplayRequest
    {
        public ReplayRequestType type;
        public int game_id;
        public ReplayCommand command;
        public float replay_speed;
    }

    public enum ReplayResponseType
    {
        NONE = 0,
        REPLAY_STARTED,
        REPLAY_INFO,
    }

    [Serializable]
    public class ReplayResponse
    {
        public ReplayResponseType type;
        public ReplayInfo info;
    }
}