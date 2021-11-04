using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class UnityAssetSource : IAssetSource
{
    // Maps IAssetSource.AssetId to resource paths in Unity.
    // Must be kept in order with the enum definitions in IAssetSource.
    private static readonly string[] assetPaths = new string[]{
        "Prefab/Actors/Player",
        "Prefab/Actors/PlayerWithCam",
        "Prefab/Tiles/GroundTile_1",
        "Prefab/Tiles/GroundTile_Rocky_1",
        "Prefab/Tiles/GroundTile_Stones_1",
        "Prefab/Tiles/GroundTile_Trees_1",
        "Prefab/Tiles/GroundTile_Trees_2",
        "Prefab/Tiles/GroundTile_Forest",
        "Prefab/Tiles/GroundTile_House",
        "Prefab/Tiles/GroundTile_StreetLight",
        "Prefab/Mountain/M_Mountain_0Side",
        "Prefab/Tiles/RampTile",
        "Prefab/Cards/CardBase_1",
        "Prefab/Cards/CardBase_2",
        "Prefab/Cards/CardBase_3",
        "Prefab/Cards/Shapes/Square",
        "Prefab/Cards/Shapes/Star",
        "Prefab/Cards/Shapes/Torus",
        "Prefab/Cards/Shapes/Triangle",
        "Prefab/Cards/Shapes/Plus",
        "Prefab/Cards/Shapes/Heart",
        "Prefab/Cards/Shapes/Diamond",
    };

    // Maps IAssetSource.MaterialId to resource paths in Unity.
    // Must be kept in order with the enum definitions in IAssetSource.
    private static readonly string[] materialPaths = new string[] {
        "Prefab/Cards/Materials/Card",
        "Prefab/Cards/Materials/card_black",
        "Prefab/Cards/Materials/card_blue",
        "Prefab/Cards/Materials/card_green",
        "Prefab/Cards/Materials/card_orange",
        "Prefab/Cards/Materials/card_pink",
        "Prefab/Cards/Materials/card_red",
        "Prefab/Cards/Materials/card_yellow",
    };

    public GameObject Load(IAssetSource.AssetId assetId)
    {
        int assetIndex = (int)assetId;
        GameObject obj = Resources.Load<GameObject>(assetPaths[assetIndex]);
        if (obj == null)
        {
            Debug.Log("Null: " + assetPaths[assetIndex]);
        }
        return obj;
    }

    public Material LoadMat(IAssetSource.MaterialId materialId)
    {
        int materialIndex = (int)materialId;
        Material mat = Resources.Load<Material>(materialPaths[materialIndex]);
        if (mat == null)
        {
            Debug.Log("Null: " + materialPaths[materialIndex]);
        }
        return mat;
    }
}