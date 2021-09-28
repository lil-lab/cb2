using System.Collections;
using System.Collections.Generic;
using System;
using UnityEngine;

// This class is a combination of a HecsCoord, size scale, and HexBoundary.
public class HexCell
{
    public HecsCoord coord;
    public HexBoundary boundary;

    public HexCell(HecsCoord c, HexBoundary b)
    {
        coord = c;
        boundary = b;
    }

    public Vector3[] Vertices()
    {
        (float cx, float cz) = coord.Cartesian();
        float cy = 0.0f;
        Vector3[] vertices = new Vector3[6];
        // Vertices starting from the top, clockwise around.
        for (int i = 0; i < 6; ++i)
        {
            float angle = 60 * i;
            (float offsetx, float offsety) = RotationOffset(angle);
            vertices[i] = new Vector3(cx + offsetx, cy, cz + offsety);
        }
        return vertices;
    }

    public Vector3 Center()
    {
        (float cx, float cz) = coord.Cartesian();
        return Scale() * (new Vector3(cx, 0, cz));
    }

    private float Scale()
    {
        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        HexGrid manager = obj.GetComponent<HexGrid>();
        return manager.Scale;
    }

    // Angle is defined as degrees from direct north, clockwise.
    private (float, float) RotationOffset(float angle)
    {
        // Adjust s.t. 0 degrees = facing north & clockwise = increasing.
        float angleAdjusted = 90 - angle;
        return ((float)(Scale() * Math.Cos(angleAdjusted)), (float)(Scale() * Math.Sin(angleAdjusted)));
    }
}
