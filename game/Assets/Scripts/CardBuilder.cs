using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

// This builder class is used to generated card props. Cards lay flat on the ground
// face-up with 1-3 shapes on them. The shapes are all the same color. Cards are built
// up as a GameObject hierarchy and then internally represented as Prop objects.
public class CardBuilder
{
    [Serializable]
    public enum Shape
    {
        NONE = 0,
        PLUS,
        TORUS,
        HEART,
        DIAMOND,
        SQUARE,
        STAR,
        TRIANGLE,
    }

    [Serializable]
    public enum Color
    {
        NONE = 0,
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
    private int _count;
    private HecsCoord _location;
    private GameObject _cardAssembly;

    public static CardBuilder FromNetwork(Network.Prop netProp)
    {
        if (netProp.PropType != Network.PropType.CARD)
        {
            Debug.Log("Warning, attempted to initialize card from non-card prop.");
            return null;
        }
        CardBuilder cardBuilder = new CardBuilder();
        cardBuilder.SetPropId(netProp.Id)
                   .SetRotationDegrees(netProp.PropInfo.RotationDegrees)
                   .SetLocation(netProp.PropInfo.Location)
                   .SetShape(netProp.CardInit.Shape)
                   .SetColor(netProp.CardInit.Color)
                   .SetCount(netProp.CardInit.Count);
        return cardBuilder;
    }

    public CardBuilder()
    {
        // Populate optional fields with defaults.
        _rotationDegrees = 0;
        _location = new HecsCoord(0, 0, 0);

        // Populate required fields with invalid values s.t. we can
        // error if the card is not fully specified.
        _propId = -1;
        _shape = Shape.NONE;
        _color = Color.NONE;
        _count = -1;
    }

    public CardBuilder SetPropId(int id)
    {
        _propId = id;
        return this;
    }

    public CardBuilder SetShape(Shape shape)
    {
        _shape = shape;
        return this;
    }

    public CardBuilder SetColor(Color color)
    {
        _color = color;
        return this;
    }

    public CardBuilder SetCount(int count)
    {
        _count = count;
        return this;
    }

    public CardBuilder SetLocation(HecsCoord location)
    {
        _location = location;
        return this;
    }

    public CardBuilder SetRotationDegrees(int rotationDegrees)
    {
        _rotationDegrees = rotationDegrees;
        return this;
    }

    public Prop Build()
    {
        // Adding a parent object to the Card GameObject allows the card's asset local transform
        // to be preserved (as otherwise Prop will overwrite the transform to place the card in 
        // its assigned location).
        GameObject cardSlot = new GameObject("CardSlot");
        GameObject card = LoadCard(_shape, _color, _count);
        card.transform.SetParent(cardSlot.transform);
        Prop prop = new Prop(cardSlot);
        prop.AddAction(Init.InitAt(_location, _rotationDegrees));
        return prop;
    }

    private GameObject LoadCard(Shape shape, Color color, int count)
    {
        // Generates a card. Each card displays 1-3 symbols of a given shape and color.
        UnityAssetSource assets = new UnityAssetSource();
        IAssetSource.AssetId cardAsset = IAssetSource.AssetId.CARD_BASE_1;
        if (count == 2)
            cardAsset = IAssetSource.AssetId.CARD_BASE_2;
        if (count == 3)
            cardAsset = IAssetSource.AssetId.CARD_BASE_3;
        GameObject card = GameObject.Instantiate(assets.Load(cardAsset));
        // The card base prefab has some empty children objects.  Each empty child has 
        // a Transform component. The component specifies where a symbol should go.
        var symbolLocations = card.GetComponentsInChildren<Transform>();
        foreach (Transform loc in symbolLocations)
        {
            // Ignore the parent object Transform.
            if (loc.gameObject.tag == "Card")
                continue;

            GameObject symbol = GameObject.Instantiate(LoadShape(shape), loc);

            // Rotate the triangle by 90 degrees.
            // TODO(sharf): Prebake this into the triangle asset.
            if (shape == Shape.TRIANGLE)
            {
                symbol.transform.Rotate(new Vector3(180f, 0f, 0f));
            }

            try
            {
                symbol.GetComponent<Renderer>().material = LoadMaterialFromColor(color);
            }
            catch
            {
                symbol.GetComponentInChildren<Renderer>().material = LoadMaterialFromColor(color);
            }
            symbol.transform.SetParent(card.transform);
        }
        if (card == null)
            Debug.LogWarning("Null card instantiated????");
        return card;
    }

    private GameObject LoadShape(Shape shape)
    {
        UnityAssetSource source = new UnityAssetSource();
        switch (shape)
        {
            case Shape.SQUARE:
                return source.Load(IAssetSource.AssetId.SQUARE);
            case Shape.STAR:
                return source.Load(IAssetSource.AssetId.STAR);
            case Shape.TORUS:
                return source.Load(IAssetSource.AssetId.TORUS);
            case Shape.TRIANGLE:
                return source.Load(IAssetSource.AssetId.TRIANGLE);
            case Shape.PLUS:
                return source.Load(IAssetSource.AssetId.PLUS);
            case Shape.HEART:
                return source.Load(IAssetSource.AssetId.HEART);
            case Shape.DIAMOND:
                return source.Load(IAssetSource.AssetId.DIAMOND);
            default:
                Debug.LogWarning("Encountered unknown Shape.");
                return null;
        }
    }

    private Material LoadMaterialFromColor(Color color)
    {
        UnityAssetSource source = new UnityAssetSource();
        switch (color)
        {
            case Color.BLACK:
                return source.LoadMat(IAssetSource.MaterialId.SHAPE_BLACK);
            case Color.BLUE:
                return source.LoadMat(IAssetSource.MaterialId.SHAPE_BLUE);
            case Color.GREEN:
                return source.LoadMat(IAssetSource.MaterialId.SHAPE_GREEN);
            case Color.ORANGE:
                return source.LoadMat(IAssetSource.MaterialId.SHAPE_ORANGE);
            case Color.PINK:
                return source.LoadMat(IAssetSource.MaterialId.SHAPE_PINK);
            case Color.RED:
                return source.LoadMat(IAssetSource.MaterialId.SHAPE_RED);
            case Color.YELLOW:
                return source.LoadMat(IAssetSource.MaterialId.SHAPE_YELLOW);
            default:
                Debug.LogWarning("Encountered unknown Color.");
                return null;
        }
    }
}
