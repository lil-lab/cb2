using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class UnityAssetSource : HexGridManager.IAssetSource
{
    public enum Assets
    {
	     GROUND_TILE,
	     GROUND_TILE_ROCKY,
	     GROUND_TILE_STONES,
	     GROUND_TILE_TREES,
	     GROUND_TILE_TREES_2,
	     GROUND_TILE_FOREST,
	     GROUND_TILE_HOUSE,
	     GROUND_TILE_STREETLIGHT,
    }

    private static readonly string[] assetPaths = new string[]{
        // TODO(sharf): Add prefab resource paths here...
        "Prefab/Tiles/GroundTile_1",
        "Prefab/Tiles/GroundTile_Rocky_1",
        "Prefab/Tiles/GroundTile_Stones_1",
        "Prefab/Tiles/GroundTile_Trees_1",
        "Prefab/Tiles/GroundTile_Trees_2",
        "Prefab/Tiles/GroundTile_Forest",
        "Prefab/Tiles/GroundTile_House",
        "Prefab/Tiles/GroundTile_StreetLight",
    };

    public GameObject Load(int assetId)
    {
        GameObject obj = Resources.Load<GameObject>(assetPaths[assetId]);
        if (obj == null) {
            Debug.Log("Null: " + assetPaths[assetId]);
	    }
        return obj;
    }
}