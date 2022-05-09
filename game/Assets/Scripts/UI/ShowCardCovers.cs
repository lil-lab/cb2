using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ShowCardCovers : MonoBehaviour
{
    // Start is called before the first frame update
    void Start()
    {
        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();
        Camera camera = GetComponent<Camera>();
        if (networkManager.ServerConfig() != null && networkManager.ServerConfig().card_covers)
        {
            camera.cullingMask = camera.cullingMask | (1 << LayerMask.NameToLayer("card_covers"));
        } else {
            camera.cullingMask = camera.cullingMask & ~(1 << LayerMask.NameToLayer("card_covers"));
        }
    }
}