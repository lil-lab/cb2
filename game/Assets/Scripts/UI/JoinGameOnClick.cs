using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;

// This redirects the JoinGame click handler to the NetworkManager.
// This is needed because the NetworkManager is a singleton, and the
// UnityEventSystem will instead reference the NetworkManager that gets created
// in the scene (which, if not the original instance, destroys itself).
public class JoinGameOnClick : MonoBehaviour, IPointerClickHandler
{
    public void OnPointerClick(PointerEventData eventData)
    {
        Debug.Log("[DEBUG]OnPointerClick -> NetworkManager.Instance.JoinGame();");
        Network.NetworkManager.Instance.JoinGame();
    }
}
