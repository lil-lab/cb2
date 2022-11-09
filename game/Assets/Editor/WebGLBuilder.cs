using System.Collections;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
class WebGLBuilder
{
    // Documentation for build options:
    // https://docs.unity3d.com/ScriptReference/BuildOptions.html
    public static void Build()
    {
        // Place all your scenes here
        string[] scenes = {
        "Assets/Scenes/menu_scene.unity",
        "Assets/Scenes/game_scene.unity",
        "Assets/Scenes/map_viewer.unity",
        "Assets/Scenes/replay_scene.unity",
        "Assets/Scenes/tutorial_scene.unity"
    };

        string pathToDeploy = "builds/WebGLVersion/";

        BuildPipeline.BuildPlayer(scenes, pathToDeploy, BuildTarget.WebGL, BuildOptions.None);
    }
}
