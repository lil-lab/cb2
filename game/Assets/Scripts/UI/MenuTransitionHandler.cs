using System.Collections;
using System.Collections.Generic;
using Network;
using UnityEngine;
using UnityEngine.UI;

public class MenuTransitionHandler : MonoBehaviour
{
    public static readonly string TAG = "MenuTransitionHandler";

    public enum MenuState
    {
        NONE,
        ESCAPE_MENU,
    }

    private static readonly string ESCAPE_MENU_TAG = "ESCAPE_MENU";

    private static readonly string INPUT_FIELD_TAG = "MessageInputField";
    private static readonly string CHAT_LOG_TAG = "ChatLog";
    private static readonly string SCROLL_VIEW_TAG = "ScrollView";

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

    public void DisplayMessage(string sender, string message)
    {
        GameObject obj = GameObject.FindWithTag(CHAT_LOG_TAG);
        if (obj == null)
        {
            Debug.Log("Could not find chat log!");
            return;
        }
        TMPro.TMP_Text chatLog = obj.GetComponent<TMPro.TMP_Text>();

        // Add a new line to the log, unless this is the first line.
        if (chatLog.text.Length > 0)
        {
            chatLog.text += "\n";
        }
        chatLog.text += "<" + sender + ">: " + message;

        // Before we move the scrollview to the bottom, the text needs to be
        // re-rendered so that the new chat log height is accounted for. Without
        // this it's off by about 20 pixels.
        Canvas.ForceUpdateCanvases();

        // Scroll to the bottom of the chat history to display the new message.
        GameObject scrollObj = GameObject.FindWithTag(SCROLL_VIEW_TAG);
        scrollObj.GetComponent<ScrollRect>().verticalScrollbar.GetComponent<Scrollbar>().value = 0;
    }

    public void SendMessage()
    {
        // Get the text entered by the user.
        GameObject textObj = GameObject.FindWithTag(INPUT_FIELD_TAG);
        TMPro.TMP_Text textMeshPro = textObj.GetComponent<TMPro.TMP_Text>();
        string text = textMeshPro.text;

        // Load the NetworkManager.
        GameObject obj = GameObject.FindWithTag(Network.NetworkManager.TAG);
        if (obj == null)
        {
            Debug.Log("Could not find network manager!");
            return;
        }
        Network.NetworkManager networkManager = obj.GetComponent<Network.NetworkManager>();
        networkManager.SendMessage(text);
        textMeshPro.text = "";
    }

    // Start is called before the first frame update
    void Start()
    {
        _currentMenuState = MenuState.NONE;
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
                _currentMenuState = MenuState.ESCAPE_MENU;
                esc_menu.GetComponent<Canvas>().enabled = true;
                Debug.Log("Opening esc menu");
                Cursor.visible = true;
            }
            else if (_currentMenuState == MenuState.ESCAPE_MENU)
            {
                _currentMenuState = MenuState.NONE;
                esc_menu.GetComponent<Canvas>().enabled = false;
                Debug.Log("Closed esc menu");
                //Set Cursor to not be visible
                Cursor.visible = false;
            }
        }
    }
}
