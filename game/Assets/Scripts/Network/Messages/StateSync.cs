using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class StateSync
    {
        [Serializable]
        public class Actor
        {
            public int actor_id;
            public int asset_id;
            public HecsCoord location;
            public float rotation_degrees;
        }

        // The total number of actors.
        public int population;

        // A list of actor initial states.
        public List<Actor> actors;

        // Which actor we are. -1 means spectate mode (no active player).
        public int player_id;
    }
}  // namespace Network
