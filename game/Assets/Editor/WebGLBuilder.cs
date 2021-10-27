using System.Collections;
using System.Collections.Generic;
using UnityEngine;

using UnityEditor;
class WebGLBuilder
{
    // Documentation for build options:
    // https://docs.unity3d.com/ScriptReference/BuildOptions.html
    public static void Build()
    {

        // Place all your scenes here
        string[] scenes = { "Assets/Scenes/game_scene.unity" };

        string pathToDeploy = "builds/WebGLVersion/";

        BuildPipeline.BuildPlayer(scenes, pathToDeploy, BuildTarget.WebGL, BuildOptions.None);
    }
}
