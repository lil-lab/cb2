using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Card
{
	[Serializable]
    public enum Shape
	{
		PLUS=0,
	    TORUS,
	    HEART,
	    DIAMOND,
	    CUBE,
	    STAR,
	    TRIANGLE,
	}

	[Serializable]
    public enum Color
	{
		BLACK,
	    BLUE,
	    GREEN,
	    ORANGE,
	    PINK,
	    RED,
	    YELLOW,
	}

	private int _propId;
    private int _rotationDegrees;  // In even multiples of 60 degrees.
    private Shape _shape;
    private Color _color;
    private HecsCoord _location;
	private GameObject _cardAssembly;

	public static Card FromNetworkCard(Network.StateSync.Prop netProp)
	{
		if (netProp.PropType != Network.PropType.CARD)
		{
			Debug.Log("Warning, attempted to initialize card from non-card prop.");
			return null;
		}
		return new Card(
			netProp.PropId,
			netProp.PropInfo.RotationDegrees,
			netProp.CardInit.Shape,
			netProp.CardInit.Color,
			netProp.PropInfo.Location
	    );
    }

    private Card(int propId, int rotation, Shape shape, Color color, HecsCoord location)
	{
		_propId = propId;
		_rotationDegrees = rotation;
		_shape = shape;
		_color = color;
		_location = location;
		_cardAssembly = GenCard(_shape, _color);
	}

	private GameObject GenCard(Shape shape, Color color)
	{
		GameObject obj = new GameObject();
		return obj;
    }
}
