using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class ToggleIfFollower : MonoBehaviour
{
    // Start is called before the first frame update
    void Start()
    {
        GameObject obj = GameObject.FindWithTag(Network.NetworkManager.TAG);
        Network.NetworkManager network = Network.NetworkManager.TaggedInstance();
        if (network == null)
        {
            Debug.Log("No network manager found.");
            return;
        }
        Toggle toggle = gameObject.GetComponent<Toggle>();
        if (toggle == null)
        {
            Debug.Log("Couldn't find toggle on attached GameObject.");
            return;
        }
        if (network.Role() == Network.Role.FOLLOWER)
        {
            toggle.interactable = true;
        }
        else
        {
            toggle.interactable = false;
        }
    }
}
