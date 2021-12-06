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
        OUTLINE,
    }

    [Serializable]
    public enum AnimationType
    {
        NONE = 0,
        IDLE,
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
        public float Rotation;  // Degrees.
        public float BorderRadius;  // Outline radius.
        public float DurationS;
        public string Expiration;  // DateTime in ISO 8601.
    }
}  // namespace Network