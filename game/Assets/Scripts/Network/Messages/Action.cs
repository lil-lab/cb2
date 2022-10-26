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
        DEATH,
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

        public Color(float r_init, float g_init, float b_init, float a_init)
        {
            r = r_init;
            g = g_init;
            b = b_init;
            a = a_init;
        }

        // Of course, a Unity Color conversion function.
        public UnityEngine.Color ToUnity()
        {
            return new UnityEngine.Color(r, g, b, a);
        }

        public override string ToString()
        {
            return string.Format("({0}, {1}, {2}, {3})", r, g, b, a);
        }

        // RGBA. Floating point. 0 to 1.
        public float r;
        public float g;
        public float b;
        public float a;
    }

    [Serializable]
    public class Action
    {
        public int id;
        public ActionType action_type;
        public AnimationType animation_type;
        public HecsCoord displacement;
        public float rotation;  // Degrees.
        public float border_radius;  // Outline radius.
        public Color border_color;  // Outline color.
        public float opacity;  // Used to animate some UI elements.
        public float duration_s;
        public string expiration;  // DateTime in ISO 8601.
        public Color border_color_follower_pov;  // Outline color from follower's POV.
    }
}  // namespace Network