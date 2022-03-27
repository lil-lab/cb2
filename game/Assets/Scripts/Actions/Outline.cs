using System;
using UnityEngine;

public class Outline : ActionQueue.IAction
{
    public static Outline Select(float radius, Network.Color borderColor, float durationS)
    {
        return new Outline(
            new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.NONE,
                Displacement = HecsCoord.ORIGIN,
                Rotation = 0,
                BorderRadius = radius,
                BorderColor = borderColor,
                DurationS = durationS,
                Expiration = DateTime.Now.AddSeconds(10),
            }
        );
    }
    public static Outline Select(float radius, float durationS)
    {
        return new Outline(
            new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.NONE,
                Displacement = HecsCoord.ORIGIN,
                Rotation = 0,
                BorderRadius = radius,
                BorderColor = Network.Color.Blue,
                DurationS = durationS,
                Expiration = DateTime.Now.AddSeconds(10),
            }
        );
    }

    public static Outline Unselect(float durationS)
    {
        return new Outline(
            new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.NONE,
                Displacement = HecsCoord.ORIGIN,
                Rotation = 0,
                BorderRadius = 0,
                BorderColor = Network.Color.Blue,
                DurationS = durationS,
                Expiration = DateTime.Now.AddSeconds(10),
            }
        );
    }

    private ActionQueue.ActionInfo _info;

    public Outline(ActionQueue.ActionInfo info)
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
        interp.BorderRadius = Mathf.Lerp(initialConditions.BorderRadius, end.BorderRadius, progress);
        interp.BorderColor = _info.BorderColor;  // Never interpolate colors.
        interp.Animation = _info.Type;
        return interp;
    }

    public State.Discrete Transfer(State.Discrete s)
    {
        s.BorderRadius = _info.BorderRadius;
        s.BorderColor = _info.BorderColor;
        return s;
    }

    public Network.Action Packet(int id)
    {
        return new Network.Action()
        {
            id = id,
            action_type = Network.ActionType.OUTLINE,
            animation_type = (Network.AnimationType)_info.Type,
            displacement = HecsCoord.ORIGIN,
            rotation = _info.Rotation,
            duration_s = _info.DurationS,
            border_radius = _info.BorderRadius,
            border_color = _info.BorderColor,
            opacity = _info.Opacity,
            expiration = _info.Expiration.ToString("o"),
        };
    }
}

