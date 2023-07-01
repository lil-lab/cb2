using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

public class SelectableUIElement : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler
{
    public Color onMouseOverColor = Color.yellow;
    public Color defaultColor = Color.white;

    public void OnPointerEnter(PointerEventData eventData)
    {
        Text t = gameObject.GetComponent<Text>();
        if (t != null)
        {
            t.color = onMouseOverColor;
        }
        TMPro.TMP_Text tmpro = gameObject.GetComponent<TMPro.TMP_Text>();
        if (tmpro != null)
        {
            tmpro.color = onMouseOverColor;
        }
    }

    public void OnPointerExit(PointerEventData eventData)
    {
        Text t = gameObject.GetComponent<Text>();
        if (t != null)
        {
            t.color = defaultColor;
        }
        TMPro.TMP_Text tmpro = gameObject.GetComponent<TMPro.TMP_Text>();
        if (tmpro != null)
        {
            tmpro.color = defaultColor;
        }
    }
}