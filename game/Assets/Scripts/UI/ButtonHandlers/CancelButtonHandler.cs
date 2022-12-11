using System.Collections;
using System.Collections.Generic;
using System;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class CancelButtonHandler : MonoBehaviour, IPointerDownHandler, IPointerUpHandler
{
    private DateTime _onMouseDownTime;
    private static readonly string CANCEL_RING_TAG = "CANCEL_LOADING_RING";
    private static readonly int CANCEL_HOLD_SECONDS = 1;

    private void StartHoldTimerIfAllowed()
    {
        // Don't allow cancellation (interruption) if it's currently our turn.
        Network.NetworkManager network = Network.NetworkManager.TaggedInstance();
        if (network.Role() == network.CurrentTurn()) {
            return;
        }
        if (_onMouseDownTime == DateTime.MinValue) {
            _onMouseDownTime = DateTime.Now;
        }
    }

    private void ClearHoldTimer()
    {
        _onMouseDownTime = DateTime.MinValue;
    }

    public void OnPointerDown(PointerEventData eventData)
    {
        StartHoldTimerIfAllowed();
    }

    public void OnPointerUp(PointerEventData pointerEventData)
    {
        ClearHoldTimer();
        var cancelRing = GameObject.FindGameObjectWithTag(CANCEL_RING_TAG);
        if (cancelRing != null)
        {
            cancelRing.GetComponent<Image>().fillAmount = 0.0f;
        }
    }

    public void Update()
    {
        if (Input.GetKeyDown(KeyCode.Tab) || Input.GetKeyDown(KeyCode.Q))
        {
            StartHoldTimerIfAllowed();
        }
        if (Input.GetKeyUp(KeyCode.Tab) || Input.GetKeyUp(KeyCode.Q))
        {
            ClearHoldTimer();
            var cancelRing = GameObject.FindGameObjectWithTag(CANCEL_RING_TAG);
            if (cancelRing != null)
            {
                cancelRing.GetComponent<Image>().fillAmount = 0.0f;
            }
        }
        if (_onMouseDownTime != DateTime.MinValue)
        {
            var timeSinceMouseDown = DateTime.Now - _onMouseDownTime;
            var cancelRing = GameObject.FindGameObjectWithTag(CANCEL_RING_TAG);
            if (cancelRing != null)
            {
                cancelRing.GetComponent<Image>().fillAmount = (float)timeSinceMouseDown.TotalSeconds / CANCEL_HOLD_SECONDS;
            }
            if (timeSinceMouseDown.TotalSeconds > CANCEL_HOLD_SECONDS)
            {
                MenuTransitionHandler.TaggedInstance().CancelPendingObjectives();
                ClearHoldTimer();
                if (cancelRing != null)
                {
                    cancelRing.GetComponent<Image>().fillAmount = 0.0f;
                }
            }
        }
     }
}
