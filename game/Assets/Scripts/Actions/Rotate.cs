using System;
using UnityEngine;

public class Rotate : ActionQueue.IAction
{
    private ActionQueue.ActionInfo _info;
    private float _heading;
    private DateTime _start;
    private HexGrid _grid;

    public Rotate(ActionQueue.ActionInfo info)
    {
        _info = info;
        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        _grid = obj.GetComponent<HexGrid>();
    }

    public void Start()
    {
        _start = DateTime.Now;
    }

    public ActionQueue.ActionInfo Info() { return _info; }

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
        return new Vector3(x, _grid.Height(_info.Start), z);
    }

    public bool IsDone()
    {
        if ((DateTime.Now - _start).TotalSeconds > _info.DurationS) return true;
        if (DateTime.Now > _info.Expiration) return true;
        return false;
    }
}

