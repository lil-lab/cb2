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
            public int ActorId;
            public int AssetId;
            public HecsCoord Location;
            public float RotationDegrees;
        }

        // The total number of actors.
        public int Population;

        // A list of actor initial states.
        public List<Actor> Actors;

        // Which actor we are. -1 means spectate mode (no active player).
        public int PlayerId;
    }
}  // namespace Network
