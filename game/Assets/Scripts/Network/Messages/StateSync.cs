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
            public HecsCoord Start;
            public int RotationDegrees;
	    }

        // A list of current actors in the world.
        public List<Actor> Actors;

        // Which actor we are. -1 means spectate mode (no active player).
        public int PlayerId;
    }
}  // namespace Network
