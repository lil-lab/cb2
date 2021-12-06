using UnityEngine;
using UnityEngine.Rendering.PostProcessing;
 
 [RequireComponent(typeof(Camera))]
 public class DisableFogOnCameraIfLeader : MonoBehaviour
 {
     private bool FogOn;

    void Start()
    {
        GameObject obj = GameObject.FindGameObjectWithTag(Network.NetworkManager.TAG);
        if (obj == null)
            return;
        Network.NetworkManager network = obj.GetComponent<Network.NetworkManager>();
        if (network == null)
            return;
        if (network.Role() == Network.Role.LEADER)
            gameObject.GetComponent<PostProcessLayer>().fog.enabled = false;
    }
 }