using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class ExpandHideParent : MonoBehaviour, IPointerClickHandler
{
    public string summary_text = "Keyboard Shorcuts... ";
    // Start is called before the first frame update
    public bool StartCollapsed = false;
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
        GameObject grandParent = gameObject.transform.parent.parent.gameObject;
        grandParent.GetComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.MinSize;
        _hidden = true;
    }

    private void Expand()
    {
        if (!_hidden) return;  // Already collapsed.
        GameObject grandParent = gameObject.transform.parent.parent.gameObject;
        grandParent.GetComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;
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
