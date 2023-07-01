using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class MapLoader : MonoBehaviour
{
    // Start is called before the first frame update
    void Start()
    {
        if (Network.NetworkManager.TaggedInstance() == null)
        {
            return;
        }
        Network.NetworkManager.TaggedInstance().RequestMapSample();        
    }
}
