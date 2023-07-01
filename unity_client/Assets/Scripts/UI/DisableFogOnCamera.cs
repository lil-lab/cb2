// This script lets you enable/disable fog per camera.
// by enabling or disabling the script in the title of the Inspector
// you can turn fog on or off per camera.

using UnityEngine;
using System.Collections;

public class DisableFogOnCamera : MonoBehaviour
{
    private bool revertFogState = false;

    void OnPreRender()
    {
        revertFogState = RenderSettings.fog;
        RenderSettings.fog = false;
    }

    void OnPostRender()
    {
        RenderSettings.fog = revertFogState;
    }
}