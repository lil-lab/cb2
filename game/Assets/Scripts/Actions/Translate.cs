﻿using System;
using UnityEngine;

public class Translate : HexAction.IAction
{
    private HexAction.ActionInfo _info;
    private Vector3 _location;
    private DateTime _start;
    private HexGrid _grid;

    public Translate(HexAction.ActionInfo info)
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

    public void Update()
    {
        float progress =
	        (float)((DateTime.Now - _start).TotalSeconds / _info.DurationS);
        (float sx, float sz) = _info.Start.Cartesian();
        (float dx, float dz) = _info.Destination.Cartesian();
        Vector3 startLocation = new Vector3(sx, _grid.Height(_info.Start), sz);
        Vector3 destinationLocation = new Vector3(dx, _grid.Height(_info.Destination), dz);
        _location = Vector3.Lerp(startLocation, destinationLocation, progress);
    }

    public float Heading()
    {
        return _info.StartHeading;
    }

    public Vector3 Location()
    {
        return _location;
    }

    public bool IsDone()
    {
        if (_start == null) return false;
        if ((DateTime.Now - _start).TotalSeconds > _info.DurationS) return true;
        if (DateTime.Now > _info.Expiration) return true;
        return false;
    }
}