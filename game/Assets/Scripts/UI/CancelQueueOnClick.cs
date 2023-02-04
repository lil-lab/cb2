using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class CancelQueueOnClick  : MonoBehaviour, IPointerClickHandler
{
    public void OnPointerClick(PointerEventData eventData)
    {
        Debug.Log("[DEBUG]OnPointerClick -> NetworkManager.Instance.CancelGameQueue();");
        MenuTransitionHandler.ShowMainMenu();
        Network.NetworkManager.TaggedInstance().CancelGameQueue();
    }
}
