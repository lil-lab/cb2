using System;
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
    private static readonly string OBJECTIVE_LIST = "OBJECTIVE_LIST";
    private static readonly string SCROLL_VIEW_TAG = "ScrollView";

    private static readonly string GAME_OVER_MENU = "GAME_OVER_UI";
    private static readonly string GAME_OVER_STATS = "GAME_OVER_STATS";
    private static readonly string GAME_OVER_REASON = "GAME_OVER_REASON";

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

    public static MenuTransitionHandler TaggedInstance()
    {
        GameObject obj = GameObject.FindGameObjectWithTag(MenuTransitionHandler.TAG);
        if (obj == null)
            return null;
        return obj.GetComponent<MenuTransitionHandler>();
    }

    public void QuitGame()
    {
        Network.NetworkManager.TaggedInstance().QuitGame();
    }

    public void BackToMenu()
    {
        Network.NetworkManager.TaggedInstance().ReturnToMenu();
    }


    public void RenderObjectiveList(List<Network.ObjectiveMessage> objectives)
    {
        GameObject objectivesPanel = GameObject.FindGameObjectWithTag(MenuTransitionHandler.OBJECTIVE_LIST);
        if (objectivesPanel == null)
        {
            Debug.LogError("Could not find objective list panel");
            return;
        }
        
        foreach (Transform child in objectivesPanel.transform)
        {
            Destroy(child.gameObject);
        }

        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();

        int activeIndex = -1;
        for(int i = 0; i < objectives.Count; ++i)
        {
            UnityAssetSource source = new UnityAssetSource();
            GameObject uiTemplate;
            if (objectives[i].Completed)
            {
                uiTemplate = source.LoadUi(IAssetSource.UiId.OBJECTIVE_COMPLETE);
            } else if (activeIndex == -1)
            {
                activeIndex = i;
                uiTemplate = source.LoadUi(IAssetSource.UiId.OBJECTIVE_ACTIVE);
            } else {
                uiTemplate = source.LoadUi(IAssetSource.UiId.OBJECTIVE_PENDING);
            }
            GameObject objectiveUi = Instantiate(uiTemplate) as GameObject;
            objectiveUi.transform.SetParent(objectivesPanel.transform);
            objectiveUi.transform.localScale = Vector3.one;
            objectiveUi.transform.localPosition = Vector3.zero;
            objectiveUi.transform.localRotation = Quaternion.identity;
            objectiveUi.transform.Find("Label").gameObject.GetComponent<TMPro.TMP_Text>().text = objectives[i].Text;
            if (activeIndex == i)
            {
                objectiveUi.GetComponent<UIObjectiveInfo>().Objective = objectives[i];
            }
            if ((activeIndex != -1) && (activeIndex < i))
            {
                if (networkManager.Role() == Network.Role.LEADER)
                {
                    objectiveUi.transform.Find("Label").gameObject.GetComponent<TMPro.TMP_Text>().text = "(unseen) " + objectives[i].Text;
                } else {
                    objectiveUi.transform.Find("Label").gameObject.GetComponent<TMPro.TMP_Text>().text = "(pending objective)";
                    // Only draw one "(pending objective)", even if multiple are available.
                    break;
                }
            }
        }

        Canvas.ForceUpdateCanvases();
        GameObject scrollObj = GameObject.FindGameObjectWithTag(MenuTransitionHandler.SCROLL_VIEW_TAG);
        if (scrollObj == null)
        {
            Debug.LogError("Could not find scroll view");
            return;
        }

        ScrollRect sRect = scrollObj.GetComponent<ScrollRect>();
        StartCoroutine(ApplyScrollPosition(sRect, 0.0f));
    }

    private IEnumerator ApplyScrollPosition(ScrollRect sr, float verticalPos)
    {
        yield return new WaitForEndOfFrame();
        sr.verticalNormalizedPosition = verticalPos;
        LayoutRebuilder.ForceRebuildLayoutImmediate((RectTransform)sr.transform);
    }

    public void OnCompleteObjective(ObjectiveCompleteMessage complete)
    {
        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();
        networkManager.TransmitObjectiveComplete(complete);
    }

    public void SendObjective()
    {
        ObjectiveMessage objective = new ObjectiveMessage();

        // Get the text entered by the user.
        GameObject textObj = GameObject.FindWithTag(INPUT_FIELD_TAG);
        TMPro.TMP_InputField textMeshPro = textObj.GetComponent<TMPro.TMP_InputField>();
        if (textMeshPro.text.Length == 0)
        {
            Debug.Log("No objective text entered.");
            return;
        }

        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();

        objective.Text = textMeshPro.text;
        objective.Sender = networkManager.Role();
        objective.Completed = false;

        Debug.Log("MOOOO1");
        networkManager.TransmitObjective(objective);

        // Clear the text field and unselect it.
        textMeshPro.text = "";
        EventSystem.current.SetSelectedGameObject(null);
        Debug.Log("MOOOO2");
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

    Text FindTextWithTag(string tag)
    {
        GameObject obj = GameObject.FindGameObjectWithTag(tag);
        if (obj == null)
        {
            Debug.Log("Unable to find text with tag: " + tag);
            return null;
        }
        return obj.GetComponent<Text>();
    }

    // Displays the end game menu. Optionally display an explanation.
    public void DisplayEndGameMenu(string reason="")
    {
        Canvas gameOverCanvas = FindCanvasWithTag(GAME_OVER_MENU);
        if (gameOverCanvas.enabled)
        {
            // Don't do anything if the end game menu is already displayed. Just log the reason.
            Debug.Log("Attempted to display the end game menu while already enabled. Reason: " + reason);
            return;
        }

        Text reasonText = FindTextWithTag(GAME_OVER_REASON);
        reasonText.text = reason;
        EndGame(_lastTurn);
    }

    private void EndGame(Network.TurnState state)
    {
        Canvas gameOverCanvas = FindCanvasWithTag(GAME_OVER_MENU);
        gameOverCanvas.enabled = true;

        Text score = FindTextWithTag(GAME_OVER_STATS);
        score.text = state.ScoreString();
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

        if (Input.GetKeyDown(KeyCode.Return))
        {
            SendObjective();
        }

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
