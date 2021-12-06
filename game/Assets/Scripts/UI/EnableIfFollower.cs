using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EnableIfFollower : MonoBehaviour
{
    void Start()
    {
        GameObject obj = GameObject.FindWithTag(Network.NetworkManager.TAG);
        if (obj == null)
        {
            Debug.Log("Could not find network manager!");
            gameObject.SetActive(false);
            return;
        }
        Network.NetworkManager networkManager = obj.GetComponent<Network.NetworkManager>();
        if (networkManager.Role() == Network.Role.FOLLOWER)
        {
            gameObject.SetActive(true);
        }
        else
        {
            gameObject.SetActive(false);
        }
    }
}
