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
    }

	// Returns a prefab of the requested asset.
	GameObject Load(AssetId assetId);

	// TODO(sharf): If we want to remove unity-specific interfaces entirely,
	// this interface can be rewritten to add something similar to Unity's
	// "Instantiate" function. 
}