using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EnabledIfWebGl : MonoBehaviour
{
    // Start is called before the first frame update
    void Start()
    {
        Debug.Log(Application.platform);
        gameObject.SetActive(Application.platform == RuntimePlatform.WebGLPlayer);
    }
}
