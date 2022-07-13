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
        "Prefab/Actors/CubeRobot",
        "Prefab/Tiles/GroundTile_1",
        "Prefab/Tiles/GroundTile_Rocky_1",
        "Prefab/Tiles/GroundTile_Stones_1",
        "Prefab/Tiles/GroundTile_Stones_1_greenbush",
        "Prefab/Tiles/GroundTile_Stones_1_brownbush",
        "Prefab/Tiles/GroundTile_Stones_1_greybush",
        "Prefab/Tiles/GroundTile_Tree",
        "Prefab/Tiles/GroundTile_Tree_Brown",
        "Prefab/Tiles/GroundTile_Tree_Snow",
        "Prefab/Tiles/GroundTile_Tree_DarkGreen",
        "Prefab/Tiles/GroundTile_Tree_SolidBrown",
        "Prefab/Tiles/GroundTile_Trees_1",
        "Prefab/Tiles/GroundTile_Trees_2",
        "Prefab/Tiles/GroundTile_Forest",
        "Prefab/Tiles/GroundTile_House",
        "Prefab/Tiles/GroundTile_House_red",
        "Prefab/Tiles/GroundTile_House_blue",
        "Prefab/Tiles/GroundTile_House_green",
        "Prefab/Tiles/GroundTile_House_orange",
        "Prefab/Tiles/GroundTile_House_pink",
        "Prefab/Tiles/GroundTile_House_yellow",
        "Prefab/Tiles/GroundTile_TripleHouse",
        "Prefab/Tiles/GroundTile_TripleHouse_red",
        "Prefab/Tiles/GroundTile_TripleHouse_blue",
        "Prefab/Tiles/GroundTile_StreetLight",
        "Prefab/Tiles/PathTile",
        "Prefab/Tiles/WaterTile",
        "Prefab/Mountain/M_Mountain_0Side",
        "Prefab/Tiles/RampTile",
        "Prefab/Tiles/Snowy_GroundTile_1",
        "Prefab/Tiles/Snowy_GroundTile_Trees_2",
        "Prefab/Tiles/Snowy_GroundTile_Rocky_1",
        "Prefab/Tiles/Snowy_GroundTile_Stones_1",
        "Prefab/Mountain/Snowy_M_Mountain_0Side",
        "Prefab/Tiles/Snowy_RampTile",
        "Prefab/Cards/CardBase_1",
        "Prefab/Cards/CardBase_2",
        "Prefab/Cards/CardBase_3",
        "Prefab/Mountain/Mountain_Tree",
        "Prefab/Mountain/Snowy_Mountain_Tree",
        // These are 2D shapes that appear on card faces.
        "Prefab/Cards/Shapes/Square",
        "Prefab/Cards/Shapes/Star",
        "Prefab/Cards/Shapes/Torus",
        "Prefab/Cards/Shapes/Triangle",
        "Prefab/Cards/Shapes/Plus",
        "Prefab/Cards/Shapes/Heart",
        "Prefab/Cards/Shapes/Diamond",
        // Used for indicating a location on the ground (in tutorials).
        "Prefab/ObjectGroups/GroundPulse_yellow",
        "Prefab/ObjectGroups/tutorial_indicator",
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
        "Prefab/Cards/Materials/card_outline",
    };

    // Maps IAssetSource.UiId to resource paths in Unity.
    // Must be kept in order with the enum definitions in IAssetSource.
    private static readonly string[] uiPaths = new string[] {
        "Prefab/UI/Instruction_Prefabs/ActiveObjective",
        "Prefab/UI/Instruction_Prefabs/CompletedObjective",
        "Prefab/UI/Instruction_Prefabs/PendingObjective",
        "Prefab/UI/Instruction_Prefabs/CancelledObjective",
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
    public GameObject LoadUi(IAssetSource.UiId uiId)
    {
        int uiIndex = (int)uiId;
        GameObject obj = Resources.Load<GameObject>(uiPaths[uiIndex]);
        if (obj == null)
        {
            Debug.Log("Null: " + assetPaths[uiIndex]);
        }
        return obj;
    }
}