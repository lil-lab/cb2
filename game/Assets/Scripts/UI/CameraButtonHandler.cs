using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class CameraButtonHandler : MonoBehaviour, IPointerUpHandler
{
    public void OnPointerUp(PointerEventData pointerEventData)
    {
        Player player = Player.TaggedInstance();
        if (player != null)
        {
            player.ToggleCameraIfAllowed();
        }
    }
}
