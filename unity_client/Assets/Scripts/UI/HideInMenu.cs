using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HideInMenu : MonoBehaviour
{
    void Start()
    {
        Network.NetworkManager network = Network.NetworkManager.TaggedInstance();
        gameObject.SetActive(network.Role() != Network.Role.NONE);
    }
}
