using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EnableIfLeader : MonoBehaviour
{
    void Start()
    {
        GameObject obj = GameObject.FindWithTag(Network.NetworkManager.TAG);
        if (obj == null)
        {
            Debug.Log("Could not find network manager!");
            return;
        }
        Network.NetworkManager networkManager = obj.GetComponent<Network.NetworkManager>();
        if (networkManager.Role() == Network.Role.LEADER)
        {
            gameObject.GetComponent<Renderer>().enabled = true;
        }
        else
        {
            gameObject.GetComponent<Renderer>().enabled = false;
        }
    }
}
