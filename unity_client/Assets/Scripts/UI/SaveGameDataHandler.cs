using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class SaveGameDataHandler : MonoBehaviour, IPointerUpHandler
{
    public void OnPointerUp(PointerEventData pointerEventData)
    {
        MenuTransitionHandler.TaggedInstance().SaveGameData();
    }
}
