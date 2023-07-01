using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayOnceOnLoad : MonoBehaviour
{
    // Play the attached audio source once.
    void Start()
    {
        AudioSource audio = gameObject.GetComponent<AudioSource>();
        if (audio != null)
        {
            audio.Play();
        }
    }
}
