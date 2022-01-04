using System;
using UnityEngine;

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

    // Color is 
    [Serializable]
    public class Color
    {
        // Some defaults for convenience.
        public static readonly Color White = new Color(1, 1, 1, 1);
        public static readonly Color Red = new Color(1, 0, 0, 1);
        public static readonly Color Green = new Color(0, 1, 0, 1);
        public static readonly Color Blue = new Color(0, 0, 1, 1);
        public static readonly Color Black = new Color(0, 0, 0, 1);
        public static readonly Color Yellow = new Color(1, 0.92f, 0.016f, 1);
        public static readonly Color Magenta = new Color(1, 0, 1, 1);
        public static readonly Color Cyan = new Color(0, 1, 1, 1);
        public static readonly Color Grey = new Color(0.5f, 0.5f, 0.5f, 1);
        public static readonly Color Transparent = new Color(0, 0, 0, 0);

        public Color(float r, float g, float b, float a)
        {
            R = r;
            G = g;
            B = b;
            A = a;
        }

        // Of course, a Unity Color conversion function.
        public UnityEngine.Color ToUnity()
        {
            return new UnityEngine.Color(R, G, B, A);
        }

        // RGBA. Floating point. 0 to 1.
        public float R;
        public float G;
        public float B;
        public float A;
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
        public Color BorderColor;  // Outline color.
        public float Opacity;  // Used to animate some UI elements.
        public float DurationS;
        public string Expiration;  // DateTime in ISO 8601.
    }
}  // namespace Network