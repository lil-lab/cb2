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
    private bool _covered;
    private HecsCoord _location;
    private GameObject _cardAssembly;
    private Logger _logger;

    public static CardBuilder FromNetwork(Network.Prop netProp)
    {
        if (netProp.prop_type != Network.PropType.CARD)
        {
            Debug.Log("Warning, attempted to initialize card from non-card prop.");
            return null;
        }
        CardBuilder cardBuilder = new CardBuilder();
        cardBuilder.SetPropId(netProp.id)
                   .SetRotationDegrees(netProp.prop_info.rotation_degrees)
                   .SetLocation(netProp.prop_info.location)
                   .SetShape(netProp.card_init.shape)
                   .SetColor(netProp.card_init.color)
                   .SetCount(netProp.card_init.count)
                   .SetCovered(netProp.card_init.hidden);
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
        _logger = Logger.GetOrCreateTrackedLogger("CardBuilder");
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

    public CardBuilder SetCovered(bool covered)
    {
        _covered = covered;
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
        cardSlot.transform.localScale = new Vector3(1.6f, 1, 1.6f);
        Prop prop = new Prop(cardSlot, BaseAssetId(_count));
        prop.AddAction(Init.InitAt(_location, _rotationDegrees));
        GameObject outline = card.transform.Find("outline").gameObject;
        GameObject followerOutline = card.transform.Find("follower_outline").gameObject;
        prop.SetOutline(outline);
        prop.SetFollowerOutline(followerOutline);
        Prop follower = GetFollower();
        // Fetch lobbyinfo from config to see if cards should stand up and track the follower.
        Network.LobbyInfo lobbyInfo = Network.NetworkManager.TaggedInstance().ServerLobbyInfo();
        Network.Role role = Network.NetworkManager.TaggedInstance().Role();
        if ((lobbyInfo != null) && lobbyInfo.cards_face_follower && (role == Network.Role.FOLLOWER))
        {
            prop.SetLookAtTarget(follower.GetGameObject());
        }
        GameObject cover = card.transform.Find("cover").gameObject;
        if (_covered)
        {
            cover.SetActive(true);
            prop.SetCover(cover);
        } else {
            cover.SetActive(false);
            prop.SetCover(null);
        }

        return prop;
    }
    private IAssetSource.AssetId BaseAssetId(int count)
    {
        IAssetSource.AssetId cardAsset = IAssetSource.AssetId.CARD_BASE_1;
        if (count == 2)
            cardAsset = IAssetSource.AssetId.CARD_BASE_2;
        if (count == 3)
            cardAsset = IAssetSource.AssetId.CARD_BASE_3;
        return cardAsset;
    }

    private GameObject LoadCard(Shape shape, Color color, int count)
    {
        // Generates a card. Each card displays 1-3 symbols of a given shape and color.
        UnityAssetSource assets = new UnityAssetSource();
        GameObject card = GameObject.Instantiate(assets.Load(BaseAssetId(count)));
        // The card base prefab has some empty children objects.  Each empty child has 
        // a Transform component. The component specifies where a symbol should go.
        var symbolLocations = card.GetComponentsInChildren<Transform>();
        foreach (Transform loc in symbolLocations)
        {
            // Ignore the parent object Transform.
            if (loc.gameObject.tag == "Card")
                continue;

            if (loc.name == "outline")
                continue;
            
            if (loc.name == "cover")
                continue;
            
            if (!loc.name.StartsWith("location"))
                continue;

            GameObject symbol = GameObject.Instantiate(LoadShape(shape), loc);

            // Rotate the triangle by 90 degrees.
            // TODO(sharf): Prebake this into the triangle asset.
            if (shape == Shape.TRIANGLE)
            {
                symbol.transform.Rotate(new Vector3(180f, 0f, 0f));
            }
            if ((count == 2) || (count == 3)) {
                Vector3 scale = symbol.transform.localScale;
                symbol.transform.localScale = new Vector3(0.7f * scale.x, scale.y, 0.7f * scale.z);
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
                return source.LoadMat(IAssetSource.MaterialId.COLOR_BLACK);
            case Color.BLUE:
                return source.LoadMat(IAssetSource.MaterialId.COLOR_BLUE);
            case Color.GREEN:
                return source.LoadMat(IAssetSource.MaterialId.COLOR_GREEN);
            case Color.ORANGE:
                return source.LoadMat(IAssetSource.MaterialId.COLOR_ORANGE);
            case Color.PINK:
                return source.LoadMat(IAssetSource.MaterialId.COLOR_PINK);
            case Color.RED:
                return source.LoadMat(IAssetSource.MaterialId.COLOR_RED);
            case Color.YELLOW:
                return source.LoadMat(IAssetSource.MaterialId.COLOR_YELLOW);
            default:
                Debug.LogWarning("Encountered unknown Color.");
                return null;
        }
    }

    private Prop GetFollower()
    {
        // Get the player's role from the network.
        Network.NetworkManager nm = Network.NetworkManager.TaggedInstance();
        if (nm.Role() == Network.Role.FOLLOWER)
        {
            Player p = Player.TaggedInstance();
            return p.GetProp();
        } else {
            EntityManager em = EntityManager.TaggedInstance();
            List<Actor> actors = em.Actors();
            // Can safely assume that if the list has one element, it's the follower.
            if (actors.Count >= 1)
            {
                return actors[0].GetProp();
            } else {
                Debug.LogWarning("Could not find follower.");
                return null;
            }
        }
    }
}
