using System;
using UnityEngine;

public class Fade : ActionQueue.IAction
{
    public static Fade FadeIn(float durationS)
    {
        return new Fade(
            new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.NONE,
                Displacement = HecsCoord.ORIGIN,
                Rotation = 0,
                BorderRadius = 0,
                Opacity = 1,
                DurationS = durationS,
                Expiration = DateTime.UtcNow.AddSeconds(10),
            }
        ); ;
    }

    public static Fade FadeOut(float durationS)
    {
        return new Fade(
            new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.NONE,
                Displacement = HecsCoord.ORIGIN,
                Rotation = 0,
                BorderRadius = 0,
                Opacity = 0,
                DurationS = durationS,
                Expiration = DateTime.UtcNow.AddSeconds(10),
            }
        ); ;
    }

    private ActionQueue.ActionInfo _info;

    public Fade(ActionQueue.ActionInfo info)
    {
        _info = info;
    }

    public float DurationS() { return _info.DurationS; }
    public DateTime Expiration() { return _info.Expiration; }

    public State.Continuous Interpolate(State.Discrete initialConditions, float progress)
    {
        // Cap progress at 1.0f.
        if (progress > 1.0f) progress = 1.0f;

        State.Discrete end = Transfer(initialConditions);

        State.Continuous interp = new State.Continuous();
        interp.Position = initialConditions.Vector();
        interp.HeadingDegrees = initialConditions.HeadingDegrees;
        interp.BorderRadius = initialConditions.BorderRadius;
        interp.Opacity = Mathf.Lerp(initialConditions.Opacity, end.Opacity, progress);
        interp.Animation = _info.Type;
        return interp;
    }

    public State.Discrete Transfer(State.Discrete s)
    {
        s.Opacity = _info.Opacity;
        return s;
    }

    public Network.Action Packet(int id)
    {
        return new Network.Action()
        {
            id = id,
            action_type = Network.ActionType.ROTATE,
            animation_type = (Network.AnimationType)_info.Type,
            displacement = HecsCoord.ORIGIN,
            rotation = _info.Rotation,
            duration_s = _info.DurationS,
            opacity = _info.Opacity,
            expiration = _info.Expiration.ToString("o"),
        };
    }
}

