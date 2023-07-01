using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class SaveScenarioState : MonoBehaviour, IPointerUpHandler
{
    public void OnPointerUp(PointerEventData pointerEventData)
    {
        // Send a message to the server to fetch the current scenario state.
        Network.NetworkManager.TaggedInstance().TransmitScenarioDownloadRequest();
    }
}