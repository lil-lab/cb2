using System;
using UnityEngine;

public class Rotate : HexAction.IAction
{
    private HexAction.ActionInfo _info;
    private float _heading;
    private DateTime _start;

    public Rotate(HexAction.ActionInfo info)
    {
        _info = info;
    }

    public void Start()
    {
        _start = DateTime.Now;
        Debug.Log("Dest heading: " + (_info.DestinationHeading).ToString());
    }

    public HexAction.ActionInfo Info() { return _info; }

    public void Update()
    {
        float progress =
            (float)((DateTime.Now - _start).TotalSeconds / _info.DurationS);
        _heading = Mathf.Lerp(_info.StartHeading, _info.DestinationHeading, progress);
    }

    public float Heading()
    {
        return _heading;
    }

    public Vector3 Location()
    {
        (float x, float z) = _info.Start.Cartesian();
        // TODO(sharf): Get ground y-value... refactor HexGridManager to handle
	    // HECS -> Vector3 conversion?
        return new Vector3(x, 0, z);
    }

    public bool IsDone()
    {
        if ((DateTime.Now - _start).TotalSeconds > _info.DurationS) return true;
        if (DateTime.Now > _info.Expiration) return true;
        return false;
    }
}

