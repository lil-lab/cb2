using System;
using UnityEngine;

// Interface for loading assets.
public interface IAssetSource
{
    public enum AssetId
    {
        PLAYER,
        PLAYER_WITH_CAM,
        GROUND_TILE,
        GROUND_TILE_ROCKY,
        GROUND_TILE_STONES,
        GROUND_TILE_TREES,
        GROUND_TILE_TREES_2,
        GROUND_TILE_FOREST,
        GROUND_TILE_HOUSE,
        GROUND_TILE_STREETLIGHT,
        MOUNTAIN_TILE,
        RAMP_TO_MOUNTAIN,
        CARD_BASE_1,
        CARD_BASE_2,
        CARD_BASE_3,
        // These are 2D shapes that appear on card faces.
        SQUARE,
        STAR,
        TORUS,
        TRIANGLE,
        PLUS,
        HEART,
        DIAMOND,
    }

    public enum MaterialId
    {
        CARD_BACKGROUND,
        // These are colors for the 2D shapes on card faces.
        SHAPE_BLACK,
        SHAPE_BLUE,
        SHAPE_GREEN,
        SHAPE_ORANGE,
        SHAPE_PINK,
        SHAPE_RED,
        SHAPE_YELLOW,
    }

    // Returns a prefab of the requested asset.
    GameObject Load(AssetId assetId);

    // Loads a material into memory.
    Material LoadMat(MaterialId material);

    // TODO(sharf): If we want to remove unity-specific interfaces entirely,
    // this interface can be rewritten to add something similar to Unity's
    // "Instantiate" function. 
}