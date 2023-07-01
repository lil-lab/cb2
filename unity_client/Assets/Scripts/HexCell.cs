using System.Collections;
using System.Collections.Generic;
using System;
using UnityEngine;

// This class is a combination of a HecsCoord, size scale, and HexBoundary.
[Serializable]
public class HexCell
{
    public HecsCoord coord;
    public HexBoundary boundary;
    public float height;
    public int layer;

    public HexCell(HecsCoord c, HexBoundary b, float h = 0, int l = 0)
    {
        coord = c;
        boundary = b;
        height = h;
        layer = l;
    }

    public Vector3[] Vertices()
    {
        (float cx, float cz) = coord.Cartesian();
        float cy = 0.0f;
        Vector3 center = new Vector3(cx, cy, cz);
        Vector3[] vertices = new Vector3[6];
        // Vertices starting from the top, clockwise around.
        for (int i = 0; i < 6; ++i)
        {
            float angle = 60.0f * i - 90;
            Vector3 start = new Vector3(1.0f, 0, 0);
            Quaternion quat = Quaternion.AngleAxis(angle, new Vector3(0, 1.0f, 0));
            Vector3 endpoint = Scale() * center + quat * (start * Radius());
            vertices[i] = endpoint;
        }
        return vertices;
    }

    public Vector3 Center()
    {
        (float cx, float cz) = coord.Cartesian();
        return Scale() * (new Vector3(cx, 0, cz));
    }

    // The distance between the centers of two neighbor cells.
    private float Scale()
    {
        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        if (obj == null)
        {
            return 1.0f;
        }
        HexGrid grid = obj.GetComponent<HexGrid>();
        return grid.Scale;
    }

    public float Apothem()
    {
        return Scale() / 2.0f;
    }

    public float Radius()
    {
        return 2.0f * Apothem() / Mathf.Sqrt(3);
    }
}
