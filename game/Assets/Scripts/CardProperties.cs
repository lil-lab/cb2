using System.Collections;
using System.Collections.Generic;
using UnityEngine;

/// Stores the properties for each card.
public class CardProperties:MonoBehaviour
{
    /// Each card has a material (color), a count, and a shape.
    public Material Color;
    public int Count;
    public GameObject Shape;

    /// Converts a card GameObject into a string representation (count +
    /// color + shape).
    public static string Stringify(GameObject card)
    {
      CardProperties p = card.GetComponent<CardProperties>();
      return p.Count.ToString() + " "
	         + p.Color.ToString().Split(' ')[0] + " "
	         + p.Shape.ToString().Split(' ')[0] + " "
	         + p.transform.position.ToString("f3");
    }

}
