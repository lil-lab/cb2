using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class UnityAssetSource : IAssetSource
{
    // Maps IAssetSource.AssetId to resource paths in Unity.
    private static readonly string[] assetPaths = new string[]{
        "Prefab/Actors/PlayerWithCam",
        "Prefab/Actors/Player",
        "Prefab/Tiles/GroundTile_1",
        "Prefab/Tiles/GroundTile_Rocky_1",
        "Prefab/Tiles/GroundTile_Stones_1",
        "Prefab/Tiles/GroundTile_Trees_1",
        "Prefab/Tiles/GroundTile_Trees_2",
        "Prefab/Tiles/GroundTile_Forest",
        "Prefab/Tiles/GroundTile_House",
        "Prefab/Tiles/GroundTile_StreetLight",
        "Prefab/Mountain/M_Mountain_0Side",
        "Prefab/Tiles/RampTile"
    };

    public GameObject Load(IAssetSource.AssetId assetId)
    {
        int assetIndex = (int)assetId;
        GameObject obj = Resources.Load<GameObject>(assetPaths[assetIndex]);
        if (obj == null) {
            Debug.Log("Null: " + assetPaths[assetIndex]);
	    }
        return obj;
    }
}