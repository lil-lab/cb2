// This script lets you enable fog on a specific camera.
using UnityEngine;

public class EnableFogOnCamera : MonoBehaviour
{
    private bool revertFogState = false;

    void OnPreRender()
    {
        revertFogState = RenderSettings.fog;
        RenderSettings.fog = true;
    }

    void OnPostRender()
    {
        RenderSettings.fog = revertFogState;
    }
}
