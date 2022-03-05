using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Blinks : MonoBehaviour
{
    public float speed = 5;

    void Update()
    {
        // Toggles Renderer.enabled on and off at a specified speed.
        gameObject.GetComponent<CanvasGroup>().alpha = (Mathf.Sin(Time.time * speed) > 0) ? 1.0f : 0.0f;
    }
}
