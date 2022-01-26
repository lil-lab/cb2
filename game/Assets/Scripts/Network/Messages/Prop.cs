using System;
namespace Network
{
    [Serializable]
    public class GenericPropInfo
    {
        public HecsCoord Location;
        public int RotationDegrees;  // Even multiples of 60.
        public bool Collide;  // Whether actors can collide with the prop.
        public int BorderRadius;  // The radius of the prop's outline.
        public Network.Color BorderColor;
    }

    [Serializable]
    public class CardConfig
    {
        public CardBuilder.Shape Shape;
        public CardBuilder.Color Color;
        public int Count;
        public bool Selected;
    }

    [Serializable]
    public class SimpleConfig
    {
        public int AssetId;
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
        public int Id;
        public PropType PropType;
        public GenericPropInfo PropInfo;

        // At most one member below is initialized, based on parent's PropType
        // (see PropUpdate class).
        public CardConfig CardInit;
        public SimpleConfig SimpleInit;
    }
}
