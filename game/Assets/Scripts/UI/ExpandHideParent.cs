using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;

public class ExpandHideParent : MonoBehaviour, IPointerClickHandler
{
    public string summary_text = "Keyboard Shorcuts... ";
    // Start is called before the first frame update
    public bool StartCollapsed = false;
    public int CollapsedSize = 30;

    private Vector2 _expandedSize;
    private bool _hidden = false;

    public void Start()
    {
        if (StartCollapsed)
        {
            Collapse();
        }
    }

    private void Collapse()
    {
        if (_hidden) return;  // Already collapsed.
        GameObject parent = gameObject.transform.parent.gameObject;
        _expandedSize = parent.GetComponent<RectTransform>().sizeDelta;
        parent.GetComponent<RectTransform>().sizeDelta = new Vector2(parent.GetComponent<RectTransform>().sizeDelta.x, CollapsedSize);
        parent.GetComponent<RectTransform>().ForceUpdateRectTransforms();
        _hidden = true;
    }

    private void Expand()
    {
        if (!_hidden) return;  // Already collapsed.
        GameObject parent = gameObject.transform.parent.gameObject;
        parent.GetComponent<RectTransform>().sizeDelta = _expandedSize;
        _hidden = false;
    }

    public void OnPointerClick(PointerEventData pointerEventData)
    {
        if (_hidden)
        {
            Expand();
        } else {
            Collapse();
        }
    }
}
