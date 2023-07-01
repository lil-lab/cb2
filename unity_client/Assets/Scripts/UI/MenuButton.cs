using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class MenuButton : MonoBehaviour, IPointerUpHandler
{
    public Network.ButtonCode ActionCode;

    public void OnPointerUp(PointerEventData eventData)
    {
        ButtonUtils.HandleAction(ActionCode);
    }
}
