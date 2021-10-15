using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Actors : MonoBehaviour
{
    public static string TAG = "Actors";

    private ActorManager _manager;

    private void Awake()
    {
        gameObject.tag = TAG;

        _manager = new ActorManager();
    }

    public ActorManager Manager()
    {
        if (_manager == null)
        {
            Debug.Log("Warning trying to retrieve null ActorManager.");
	    }
        return _manager;
    }
}
