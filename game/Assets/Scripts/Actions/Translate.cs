using System;
using UnityEngine;

public class Translate : ActionQueue.IAction
{
    public static Translate Walk(HecsCoord displacement, float durationS)
    {
        return new Translate(
            new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.WALKING,
                Displacement = displacement,
                Rotation = 0,
                DurationS = durationS,
                Expiration = DateTime.Now.AddSeconds(10),
            }
        );
    }

    private ActionQueue.ActionInfo _info;

    public Translate(ActionQueue.ActionInfo info)
    {
        _info = info;
    }
    
    public float DurationS() { return _info.DurationS;  }
    public DateTime Expiration() { return _info.Expiration;  }

    public State.Continuous Interpolate(State.Discrete initialConditions, float progress)
    {
        // Cap progress at 1.0f.
        if (progress > 1.0f) progress = 1.0f;

        State.Discrete end = Transfer(initialConditions);
        
        State.Continuous interp = new State.Continuous();
        interp.Position = Vector3.Lerp(initialConditions.Vector(),
	                                   end.Vector(),
	                                   progress);
        interp.HeadingDegrees = initialConditions.HeadingDegrees;
        interp.BorderRadius = initialConditions.BorderRadius;
        interp.Opacity = initialConditions.Opacity;
        interp.Animation = _info.Type;
        return interp; 
    }

    public State.Discrete Transfer(State.Discrete s)
    {
        s.Coord = HecsCoord.Add(s.Coord, _info.Displacement);
        return s;
    }

    public Network.Action Packet(int id)
    {
        return new Network.Action()
        {
            Id = id,
            ActionType = Network.ActionType.TRANSLATE,
            AnimationType = (Network.AnimationType)_info.Type,
            Displacement = _info.Displacement,
            Rotation = 0,
            DurationS = _info.DurationS,
            Expiration = _info.Expiration.ToString("o"),
        };
    }
}
