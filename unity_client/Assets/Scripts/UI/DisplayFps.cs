using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class DisplayFps : MonoBehaviour
{
    void Start()
    {
        if (!Debug.isDebugBuild)
        {
            // this.enabled = false;
        }
    }
    // Update is called once per frame
    void Update()
    {
        float fps = 1.0f / Time.deltaTime;
        GetComponent<Text>().text = "FPS: " + fps.ToString("0.00");
    }
}
