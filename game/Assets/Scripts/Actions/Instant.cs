using System;
using UnityEngine;

// Instant instantly applies the given action.
public class Instant : ActionQueue.IAction
{
    private ActionQueue.ActionInfo _info;

    public Instant(ActionQueue.ActionInfo info)
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
        interp.Animation = _info.Type;
        return interp; 
    }

    public State.Discrete Transfer(State.Discrete s)
    {
        s.Coord = HecsCoord.Add(s.Coord, _info.Displacement);
        s.HeadingDegrees += _info.Rotation;
        return s;
    }

    public Network.Action Packet(int id)
    {
        return new Network.Action()
        {
            Id = id,
            ActionType = Network.ActionType.INSTANT,
            AnimationType = (Network.AnimationType)_info.Type,
            Displacement = _info.Displacement,
            Rotation = _info.Rotation,
            DurationS = _info.DurationS,
            Expiration = _info.Expiration.ToString("o"),
        };
    }
}
