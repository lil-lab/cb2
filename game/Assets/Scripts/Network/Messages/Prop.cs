using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class GenericPropInfo
    {
        public HecsCoord location;
        public int rotation_degrees;  // Even multiples of 60.
        public bool collide;  // Whether actors can collide with the prop.
        public int border_radius;  // The radius of the prop's outline.
        public Network.Color border_color;
    }

    [Serializable]
    public class CardConfig
    {
        public CardBuilder.Shape shape;
        public CardBuilder.Color color;
        public int count;
        public bool selected;

        // If true, hides the card's state with a cover. This is used for
        // fine-grained control over which cards are visible.  If you just want
        // to disable all card covers, use the configuration option in
        // config/config.py.
        public bool hidden = false;
    }

    [Serializable]
    public class SimpleConfig
    {
        public int asset_id;
    }

    public enum PropType
    {
        NONE = 0,
        SIMPLE,  // A simple asset with little to no behavior.
        CARD,  // A card the user can activate by standing on.
    }

    [Serializable]
    public class Prop
    {
        // Always provided.
        public int id;
        public PropType prop_type;
        public GenericPropInfo prop_info;

        // At most one member below is initialized, based on parent's PropType
        // (see PropUpdate class).
        public CardConfig card_init;
        public SimpleConfig simple_init;
    }

    [Serializable]
    public class PropUpdate
    {
        public List<Prop> props;
    }
}
