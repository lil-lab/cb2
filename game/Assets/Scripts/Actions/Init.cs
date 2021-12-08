using System;

// Used to init a prop's state. Displacement and Rotation are treated as
// absolute coordinates and heading wrt HecsCoord(0, 0, 0) and Heading = 0.
// Instantly takes effect.
public class Init : ActionQueue.IAction
{
    public static Init InitAt(HecsCoord loc, float headingDegrees)
    {
        return new Init(
            new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.IDLE,
                Displacement = loc,
                Rotation = headingDegrees,
                Expiration = DateTime.Now.AddSeconds(10),
                DurationS = 0.01f,
            }
        );
    }

    private ActionQueue.ActionInfo _info;

    public Init(ActionQueue.ActionInfo info)
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
        s.Coord = _info.Displacement;
        s.HeadingDegrees = _info.Rotation;
        return s;
    }

    public Network.Action Packet(int id)
    {
        return new Network.Action()
        {
            Id = id,
            ActionType = Network.ActionType.INIT,
            AnimationType = (Network.AnimationType)_info.Type,
            Displacement = _info.Displacement,
            Rotation = _info.Rotation,
            DurationS = _info.DurationS,
            Expiration = _info.Expiration.ToString("o"),
        };
    }
}
