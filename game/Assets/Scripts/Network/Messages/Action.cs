using System;

namespace Network
{
    [Serializable]
    public enum ActionType
    {
        INIT = 0,
        INSTANT,
        ROTATE,
        TRANSLATE,
        OUTLINE_ON,
        OUTLINE_OFF,
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
        public int Id;
        public ActionType ActionType;
        public AnimationType AnimationType;
        public HecsCoord Displacement;
        public float Rotation;  // Heading Degrees. 0 = North, CW.
        public float DurationS;
        public string Expiration;  // DateTime in ISO 8601.
    }
}  // namespace Network