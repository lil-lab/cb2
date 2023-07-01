using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Breathes : MonoBehaviour
{
    public float speed = 2;

    void Update()
    {
        gameObject.GetComponent<CanvasGroup>().alpha = 0.5f * Mathf.Sin(Time.time * speed) + 0.5f;
    }
}
