using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class UnityAssetSource : HexGridManager.IAssetSource
{
    public static readonly int GROUND_TILE = 0;

    private static readonly string[] assetPaths = new string[]{
        // TODO(sharf): Add prefab resource paths here...
    };

    public GameObject Load(int assetId)
    {
        return Resources.Load<GameObject>(assetPaths[assetId]);
    }
}