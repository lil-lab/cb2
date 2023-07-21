using System;
using UnityEngine;

// See src/cb2game/server/messages/buttons.py for reference.
namespace Network
{
    [Serializable]
    public enum KeyCode {
        NONE = 0,
        LEFT = 1,
        RIGHT = 2,
        UP = 3,
        DOWN = 4,
        C = 5,
        T = 6,
        N = 7,
        G = 8,
        B = 9,
        P = 10,
        TAB = 11,
        ESCAPE = 12,
        ENTER = 13,
        W = 14,
        A = 15,
        S = 16,
        D = 17
    }

    public enum ButtonPressEvent {
        NONE = 0,
        // May be simulated -- if a key is held down but triggers an underlying
        // event multiple times, then it's sent on the event. For example if you
        // hold down the "UP" key and your character moves 3 times, 3 UP
        // keydowns will be sent.
        KEY_DOWN = 1,
        // Currently not sent by client.
        KEY_UP = 2,
        HOLD = 3,
    }

    [Serializable]
    public class ButtonPress
    {
        public Role role;
        public KeyCode button_code;
        public bool is_down;
        public ButtonPressEvent press_event;
    }
}
