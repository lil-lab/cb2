using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;

public class SendNegativeFeedbackHandler : MonoBehaviour, IPointerUpHandler
{
    public void OnPointerUp(PointerEventData pointerEventData)
    {
        MenuTransitionHandler handler = MenuTransitionHandler.TaggedInstance();
        handler.SendNegativeFeedback();
    }
}
