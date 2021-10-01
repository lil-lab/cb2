using System;
using UnityEngine;

public class Instant : HexMovement.IMovement
{
    private HexMovement.MovementInfo _info;
    private DateTime _start;

    public Instant(HexMovement.MovementInfo info)
    {
        _info = info;
    }

    public void Start()
    {
        _start = DateTime.Now;
    }

    public HexMovement.MovementInfo Info() { return _info;  }

    public void Update() { }

    public float Heading()
    {
        return _info.StartHeading;
    }

    public Vector3 Location()
    {
        (float dx, float dz) = _info.Destination.Cartesian();
        // I'm going to need to get the ground location...
        return new Vector3(dx, 0, dz);
    }

    public bool IsDone()
    {
        return true;
    }
}
