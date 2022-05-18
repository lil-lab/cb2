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
    private static readonly int CANCEL_HOLD_SECONDS = 2;


    public void OnPointerDown(PointerEventData eventData)
    {
        if (_onMouseDownTime == DateTime.MinValue) {
            _onMouseDownTime = DateTime.Now;
        }
    }

    public void OnPointerUp(PointerEventData pointerEventData)
    {
        _onMouseDownTime = DateTime.MinValue;
        var cancelRing = GameObject.FindGameObjectWithTag(CANCEL_RING_TAG);
        if (cancelRing != null)
        {
            cancelRing.GetComponent<Image>().fillAmount = 0.0f;
        }
    }

    public void Update()
    {
        if (Input.GetKeyDown(KeyCode.Tab))
        {
            _onMouseDownTime = DateTime.Now;
        }
        if (Input.GetKeyUp(KeyCode.Tab))
        {
            _onMouseDownTime = DateTime.MinValue;
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
                _onMouseDownTime = DateTime.MinValue;
                if (cancelRing != null)
                {
                    cancelRing.GetComponent<Image>().fillAmount = 0.0f;
                }
            }
        }
     }
}
