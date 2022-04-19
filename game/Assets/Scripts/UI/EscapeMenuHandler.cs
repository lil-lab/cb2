using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EscapeMenuHandler : MonoBehaviour
{

    private enum MenuState
    {
        NONE,
        ESCAPE_MENU,
    }

    private static readonly string ESCAPE_MENU_TAG = "ESCAPE_MENU";
    private static readonly string GAME_OVER_MENU = "GAME_OVER_UI";

    private MenuState _currentMenuState;

    Canvas FindCanvasWithTag(string tag)
    {
        GameObject obj = GameObject.FindGameObjectWithTag(tag);
        if (obj == null)
        {
            Debug.Log("Unable to find canvas with tag: " + tag);
            return null;
        }
        return obj.GetComponent<Canvas>();
    }


    // Update is called once per frame
    void Update()
    {
        GameObject esc_menu = GameObject.FindWithTag(ESCAPE_MENU_TAG);
        if (esc_menu == null)
        {
            Debug.Log("Could not find escape menu!");
            return;
        }

        if (Input.GetKeyDown(KeyCode.Escape))
        {
            if (_currentMenuState == MenuState.NONE)
            {
                Canvas gameOverCanvas = FindCanvasWithTag(GAME_OVER_MENU);
                if ((gameOverCanvas != null) && gameOverCanvas.enabled)
                {
                    // Don't do anything if the end game menu is already displayed.
                    return;
                }
                _currentMenuState = MenuState.ESCAPE_MENU;
                esc_menu.GetComponent<Canvas>().enabled = true;
                Debug.Log("Opening esc menu");
            }
            else if (_currentMenuState == MenuState.ESCAPE_MENU)
            {
                _currentMenuState = MenuState.NONE;
                esc_menu.GetComponent<Canvas>().enabled = false;
                Debug.Log("Closed esc menu");
            }
        }
    }
}
