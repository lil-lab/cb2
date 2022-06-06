using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class QuitGameHandler : MonoBehaviour, IPointerUpHandler
{
    public void OnPointerUp(PointerEventData pointerEventData)
    {
        Network.NetworkManager.TaggedInstance().QuitGame();
    }
}
