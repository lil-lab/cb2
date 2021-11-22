using System.Collections;
using System.Collections.Generic;
using Network;
using UnityEngine;

public class MenuTransitionHandler : MonoBehaviour
{
    public enum MenuState
    {
        NONE,
        ESCAPE_MENU,
        TAB_MENU,
    }

    private static readonly string ESCAPE_MENU_TAG = "ESCAPE_MENU";
    private static readonly string TAB_MENU_TAG = "TAB_MENU";

    private MenuState _currentMenuState;

    public void QuitGame()
    {
        GameObject obj = GameObject.FindWithTag(Network.NetworkManager.TAG);
        if (obj == null)
        {
            Debug.Log("Could not find network manager!");
            return;
        }
        Network.NetworkManager networkManager = obj.GetComponent<Network.NetworkManager>();
        networkManager.QuitGame();
    }

    // Start is called before the first frame update
    void Start()
    {
        _currentMenuState = MenuState.NONE;
    }

    // Update is called once per frame
    void Update()
    {
        if (Input.GetKeyDown(KeyCode.Escape))
        {
            if (_currentMenuState == MenuState.NONE)
            {
                _currentMenuState = MenuState.ESCAPE_MENU;
                GameObject.FindWithTag(ESCAPE_MENU_TAG).SetActive(true);
                Debug.Log("Opening esc menu");
            }
            else if (_currentMenuState == MenuState.ESCAPE_MENU)
            {
                _currentMenuState = MenuState.NONE;
                GameObject.FindWithTag(ESCAPE_MENU_TAG).SetActive(false);
                Debug.Log("Closed esc menu");
            }
        }
        else if (Input.GetKeyDown(KeyCode.Tab))
        {
            if (_currentMenuState == MenuState.NONE)
            {
                _currentMenuState = MenuState.TAB_MENU;
                GameObject.FindWithTag(TAB_MENU_TAG).SetActive(true);
            }
            else if (_currentMenuState == MenuState.TAB_MENU)
            {
                _currentMenuState = MenuState.NONE;
                GameObject.FindWithTag(TAB_MENU_TAG).SetActive(true);
            }
        }
    }
}
