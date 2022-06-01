using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class CameraButtonHandler : MonoBehaviour, IPointerDownHandler, IPointerUpHandler
{
    private bool restoreFocus = false;
    public void OnPointerDown(PointerEventData pointerEventData)
    {
        // If the currently selected object is null, restore focus on pointer up.
        restoreFocus = EventSystem.current.currentSelectedGameObject == null;
    }
    public void OnPointerUp(PointerEventData pointerEventData)
    {
        Player player = Player.TaggedInstance();
        if (player != null)
        {
            player.ToggleCameraIfAllowed();

            if (restoreFocus)
            {
                EventSystem.current.SetSelectedGameObject(null);
                restoreFocus = false;
            }
        }
    }
}
