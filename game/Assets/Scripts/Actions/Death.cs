using System;
using UnityEngine;

// Used to coordinate prop lifetime/deallocation after a certain number of
// actions have completed. Up to the ActionQueue owner
// to properly implement the EndOfLife state field.
public class Death : ActionQueue.IAction
{
    public static Death DieImmediately()
    {
        return new Death(
            new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.IDLE,
                Displacement = new HecsCoord(0, 0, 0),
                Rotation = 0,
                Expiration = DateTime.Now.AddSeconds(10),
                DurationS = 0.01f,
            }
        );
    }

    private ActionQueue.ActionInfo _info;

    public Death(ActionQueue.ActionInfo info)
    {
        _info = info;
    }
    
    public float DurationS() { return _info.DurationS;  }
    public DateTime Expiration() { return _info.Expiration;  }

    public State.Continuous Interpolate(State.Discrete initialConditions, float progress)
    {
        State.Discrete end = Transfer(initialConditions);
        
        State.Continuous interp = new State.Continuous();
        interp.Position = end.Vector();
        interp.HeadingDegrees = end.HeadingDegrees;
        interp.BorderRadius = end.BorderRadius;
        interp.Opacity = end.Opacity;
        interp.Animation = _info.Type;
        return interp; 
    }

    public State.Discrete Transfer(State.Discrete s)
    {
        s.EndOfLife = true;
        return s;
    }

    // Death packets are used to coordinate the end of an object's lifetime and
    // only come from the server. packetizing a death packet for transmission is
    // not supported
    public Network.Action Packet(int id)
    {
        Debug.LogError("Tried to packetize unsupported action type Death action.");
        return null;
    }
}
