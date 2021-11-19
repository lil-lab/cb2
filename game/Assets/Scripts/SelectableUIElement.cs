using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

public class SelectableUIElement : MonoBehaviour
{
    public Color onMouseOverColor = Color.yellow;
    public Color defaultColor = Color.white;

    public void OnPointerEnter()
    {
        gameObject.GetComponent<Text>().color = onMouseOverColor;
    }

    public void OnPointerExit()
    {
        gameObject.GetComponent<Text>().color = defaultColor;
    }
}