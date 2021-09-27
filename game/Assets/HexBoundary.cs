using System.Collections;
using System.Collections.Generic;

// Stores boundary information for a hexagon (1 bit per edge)
public class HexBoundary
{
    private byte _edges;

    private static readonly int UP_RIGHT = 0b1;
    private static readonly int RIGHT = 0b10;
    private static readonly int DOWN_RIGHT = 0b100;
    private static readonly int DOWN_LEFT = 0b1000;
    private static readonly int LEFT = 0b10000;
    private static readonly int UP_LEFT = 0b100000;

    private static readonly Dictionary<HecsCoord, int> LOC_TO_EDGE = new Dictionary<HecsCoord, int>
        {
            {HecsCoord.ORIGIN.UpRight(), UP_RIGHT},
            {HecsCoord.ORIGIN.Right(), RIGHT},
            {HecsCoord.ORIGIN.DownRight(), DOWN_RIGHT},
            {HecsCoord.ORIGIN.DownLeft(), DOWN_LEFT},
            {HecsCoord.ORIGIN.Left(), LEFT},
            {HecsCoord.ORIGIN.UpLeft(), UP_LEFT},
        };

    public HexBoundary() {}

    // Accessor methods.
    public bool UpRight() { return (_edges | UP_RIGHT) != 0; }
    public bool Right() { return (_edges | RIGHT) != 0; }
    public bool DownRight() { return (_edges | DOWN_RIGHT) != 0; }
    public bool DownLeft() { return (_edges | DOWN_LEFT) != 0; }
    public bool Left() { return (_edges | LEFT) != 0; }
    public bool UpLeft() { return (_edges | UP_LEFT) != 0; }

    // Accessor method. Takes in the cell location and a neighbor coordinate.
    // Gets the edge shared with that neighbor.
    public bool GetEdgeWith(HecsCoord loc, HecsCoord neighbor)
    {
        HecsCoord displacement = HecsCoord.Sub(neighbor, loc);
        return (_edges | LOC_TO_EDGE[displacement]) != 0;
    }

    // Mutator methods.
    public void UpRight(bool e) { SetBit(e, UP_RIGHT); }
    public void Right(bool e) { SetBit(e, RIGHT); }
    public void DownRight(bool e) { SetBit(e, DOWN_RIGHT); }
    public void DownLeft(bool e) { SetBit(e, DOWN_LEFT); }
    public void Left(bool e) { SetBit(e, LEFT); }
    public void UpLeft(bool e) { SetBit(e, UP_LEFT); }

    // Mutator method. Takes in the cell location and a neighbor coordinate.
    // Sets the edge shared with that neighbor.
    public void SetEdgeWith(HecsCoord loc, HecsCoord neighbor)
    {
        HecsCoord displacement = HecsCoord.Sub(neighbor, loc);
        SetBit(true, LOC_TO_EDGE[displacement]);
    }

    public void Clear()
    {
        _edges = 0;
    }

    // Save the current edge boundary info to a single byte.
    public byte Serialize() { return _edges; }

    // Warning, this overwrites the current edge state.
    public void Deserialize(byte edges) { _edges = edges;  }

    public void MergeWith(HexBoundary other)
    {
        _edges |= other._edges;
    }

    private void SetBit(bool val, int bit)
    {
        int binVal = (val) ? 1 : 0;
        int mask = 1 << bit;
        byte clearMask = (byte)(~mask);
        _edges &= clearMask;
        _edges |= (byte)(binVal << bit);
    }

    private int OppositeSide(int side)
    {
        side <<= 3;
        // Wraparound logic;
        if (side > UP_LEFT)
        {
            side >>= 6;
        }
        return side;
    }
}
