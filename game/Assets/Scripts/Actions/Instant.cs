﻿using System;
using UnityEngine;

public class Instant : HexAction.IAction
{
    private HexAction.ActionInfo _info;
    private DateTime _start;
    private HexGrid _grid;

    public Instant(HexAction.ActionInfo info)
    {
        _info = info;
        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        _grid = obj.GetComponent<HexGrid>();
    }

    public void Start()
    {
        _start = DateTime.Now;
    }

    public HexAction.ActionInfo Info() { return _info;  }

    public void Update() { }

    public float Heading()
    {
        return _info.StartHeading;
    }

    public Vector3 Location()
    {
        (float dx, float dz) = _info.Destination.Cartesian();
        // I'm going to need to get the ground location...
        return new Vector3(dx, _grid.Height(_info.Destination), dz);
    }

    public bool IsDone()
    {
        return true;
    }
}