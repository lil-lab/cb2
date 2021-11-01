using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class GenericPropInfo
    {
        public HecsCoord Location;
        public int RotationDegrees;  // Even multiples of 60.
        public bool Collide;  // Whether actors can collide with the prop.
    }

    [Serializable]
    public class CardConfig
    {
        public Card.Shape Shape;
        public Card.Color Color;
    }

    public enum PropType
    {
        SIMPLE=0,  // A simple asset with little to no behavior.
        CARD,  // A card the user can activate by standing on.
    }

    [Serializable]
    public class StateSync
    {
	    [Serializable]
	    public class Prop
	    {
            // Always provided.
            public int PropId;
			public PropType PropType;
			public GenericPropInfo PropInfo;

			// At most one member below is initialized, based on parent's PropType
			    // (see PropUpdate class).
			public CardConfig CardInit;
	    }

        [Serializable]
        public class Actor
        {
            public int ActorId;
            public int AssetId;
            public HecsCoord Location;
            public int RotationDegrees;
	    }

        // A list of actor initial states.
        public List<Actor> Actors;

        // Prop initial states.
        public List<Prop> Props;

        // Which actor we are. -1 means spectate mode (no active player).
        public int PlayerId;
    }
}  // namespace Network
