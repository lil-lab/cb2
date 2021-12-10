using System.Collections;
using System.Collections.Generic;
using Network;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

public class MenuTransitionHandler : MonoBehaviour
{
    public static readonly string TAG = "InGameMenuHandler";

    public enum MenuState
    {
        NONE,
        ESCAPE_MENU,
    }

    private static readonly string ESCAPE_MENU_TAG = "ESCAPE_MENU";

    private static readonly string INPUT_FIELD_TAG = "MessageInputField";
    private static readonly string CHAT_LOG_TAG = "ChatLog";
    private static readonly string SCROLL_VIEW_TAG = "ScrollView";

    private static readonly string GAME_OVER_MENU = "GAME_OVER_UI";
    private static readonly string GAME_OVER_STATS = "GAME_OVER_STATS";

    private static readonly string SCORE_TEXT_TAG = "SCORE_TEXT";
    private static readonly string OUR_TURN_TAG = "OUR_TURN_INDICATOR";
    private static readonly string NOT_OUR_TURN_TAG = "NOT_OUR_TURN_INDICATOR";

    // We re-use ActionQueue here to animate UI transparency. It's a bit
    // overkill to have two animation queues here, but it's very obvious what's
    // happening for the reader, and that's worth it.
    private ActionQueue notOurTurnIndicatorFade = new ActionQueue();
    private ActionQueue ourTurnIndicatorFade = new ActionQueue();

    private MenuState _currentMenuState;
    private TurnState _lastTurn = new TurnState();

    public void QuitGame()
    {
        Network.NetworkManager.TaggedInstance().QuitGame();
    }

    public void BackToMenu()
    {
        Network.NetworkManager.TaggedInstance().ReturnToMenu();
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
        TMPro.TMP_InputField textMeshPro = textObj.GetComponent<TMPro.TMP_InputField>();
        string text = textMeshPro.text;

        // Load the NetworkManager.
        GameObject obj = GameObject.FindWithTag(Network.NetworkManager.TAG);
        if (obj == null)
        {
            Debug.Log("Could not find network manager!");
            return;
        }

        Network.NetworkManager networkManager = obj.GetComponent<Network.NetworkManager>();
        networkManager.TransmitTextMessage(text);
        textMeshPro.text = "";

        // Unselect the text field.
        EventSystem.current.SetSelectedGameObject(null);
    }

    public void HandleTurnState(Network.TurnState state)
    {
        if (state.GameOver)
        {
            EndGame(state);
        }
        else
        {
            DisplayTurnState(state);
        }
    }

    private void DisplayTurnState(Network.TurnState state)
    {
        // Load the NetworkManager.
        GameObject obj = GameObject.FindWithTag(Network.NetworkManager.TAG);
        if (obj == null)
        {
            Debug.Log("Could not find network manager!");
            return;
        }

        Network.NetworkManager networkManager = obj.GetComponent<Network.NetworkManager>();

        string twoLineSummary = state.ShortStatus();
        GameObject scoreObj = GameObject.FindWithTag(SCORE_TEXT_TAG);
        TMPro.TMP_Text textMeshPro = scoreObj.GetComponent<TMPro.TMP_Text>();
        textMeshPro.text = twoLineSummary;

        if (_lastTurn.Turn != state.Turn)
        {
            Debug.Log("Changing turn animation. " + _lastTurn.Turn + " -> " + state.Turn);
            if (state.Turn == networkManager.Role())
            {
                notOurTurnIndicatorFade.AddAction(Fade.FadeOut(0.5f));
                ourTurnIndicatorFade.AddAction(Instant.Pause(0.5f));
                ourTurnIndicatorFade.AddAction(Fade.FadeIn(0.5f));
            }
            else
            {
                ourTurnIndicatorFade.AddAction(Fade.FadeOut(0.5f));
                notOurTurnIndicatorFade.AddAction(Instant.Pause(0.5f));
                notOurTurnIndicatorFade.AddAction(Fade.FadeIn(0.5f));
            }
        }
        _lastTurn = state;

        // Force the canvas to re-render in order to display the new text mesh.
        Canvas.ForceUpdateCanvases();
    }

    private void EndGame(Network.TurnState state)
    {
        GameObject obj = GameObject.FindWithTag(GAME_OVER_MENU);
        if (obj == null)
        {
            Debug.Log("Could not find game over menu!");
            return;
        }
        Canvas gameOverCanvas = obj.GetComponent<Canvas>();
        gameOverCanvas.enabled = true;

        GameObject scoreObj = GameObject.FindWithTag(GAME_OVER_STATS);
        Text scoreText = scoreObj.GetComponent<Text>();
        scoreText.text = state.ScoreString();
    }

    // Start is called before the first frame update
    void Start()
    {
        _currentMenuState = MenuState.NONE;
        notOurTurnIndicatorFade = new ActionQueue("NotOurTurnQueue");
        ourTurnIndicatorFade = new ActionQueue("OurTurnQueue");
    }

    // Update is called once per frame
    void Update()
    {
        // Handle UI animations.
        ourTurnIndicatorFade.Update();
        State.Continuous tS = ourTurnIndicatorFade.ContinuousState();
        GameObject turn_obj = GameObject.FindWithTag(OUR_TURN_TAG);
        CanvasGroup turn_group = turn_obj.GetComponent<CanvasGroup>();
        turn_group.alpha = tS.Opacity;

        notOurTurnIndicatorFade.Update();
        State.Continuous nTS = notOurTurnIndicatorFade.ContinuousState();
        GameObject not_turn_obj = GameObject.FindWithTag(NOT_OUR_TURN_TAG);
        CanvasGroup not_turn_group = not_turn_obj.GetComponent<CanvasGroup>();
        not_turn_group.alpha = nTS.Opacity;

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
