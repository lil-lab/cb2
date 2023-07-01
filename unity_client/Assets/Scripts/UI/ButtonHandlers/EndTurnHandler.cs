using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;

public class EndTurnHandler : MonoBehaviour, IPointerUpHandler
{
    public void OnPointerUp(PointerEventData eventData)
    {
        Logger.GetOrCreateTrackedLogger("EndTurnHandler").Info("OnPointerUp");
        MenuTransitionHandler.TaggedInstance().TurnComplete();
    }
}
