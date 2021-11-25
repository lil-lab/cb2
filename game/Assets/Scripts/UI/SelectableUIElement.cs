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
        gameObject.GetComponent<Text>().color = onMouseOverColor;
    }

    public void OnPointerExit(PointerEventData eventData)
    {
        gameObject.GetComponent<Text>().color = defaultColor;
    }
}