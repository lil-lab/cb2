using System;

namespace Network
{
    [Serializable]
    public enum ActionType
    {
        INSTANT = 0,
        ROTATE,
        TRANSLATE,
    }

    [Serializable]
    public enum AnimationType
    {
        IDLE = 0,
        WALKING,
        INSTANT,
        TRANSLATE,
        ACCEL_DECEL,
        SKIPPING,
        ROTATE,
    }

    [Serializable]
    public class Action
    {
        public int ActorId;
        public ActionType ActionType;
        public AnimationType AnimationType;
        public HecsCoord Start;
        public HecsCoord Destination;
        public float StartHeading;  // Degrees. 0 = North. Clockwise increasing.
        public float DestinationHeading;
        public float DurationS;
        public DateTime Expiration;
    }

}  // namespace Network
