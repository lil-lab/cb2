using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

public class KeyboardShortcutHandler : MonoBehaviour
{
    private static readonly string INPUT_FIELD_TAG = "MessageInputField";
    private Logger _logger;

    public void Start()
    {
        _logger = Logger.GetOrCreateTrackedLogger("KeyboardShortcutHandler");
    }

    public void SendPositiveFeedback()
    {
        MenuTransitionHandler menu = MenuTransitionHandler.TaggedInstance();
        menu.SendPositiveFeedback();
    }

    public void SendNegativeFeedback()
    {
        MenuTransitionHandler menu = MenuTransitionHandler.TaggedInstance();
        menu.SendNegativeFeedback();
    }

    public void SendObjective()
    {
        Network.ObjectiveMessage objective = new Network.ObjectiveMessage();

        // Get the text entered by the user.
        GameObject textObj = GameObject.FindWithTag(INPUT_FIELD_TAG);
        TMPro.TMP_InputField textMeshPro = textObj.GetComponent<TMPro.TMP_InputField>();
        if (textMeshPro.text.Length == 0)
        {
            Debug.Log("No objective text entered.");
            return;
        }

        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();

        objective.text = textMeshPro.text;
        objective.sender = networkManager.Role();
        objective.completed = false;
        objective.cancelled = false;

        networkManager.TransmitObjective(objective);

        // Clear the text field and unselect it.
        textMeshPro.text = "";
        EventSystem.current.SetSelectedGameObject(null);
    }

    private bool UserTypingInput()
    {
        return EventSystem.current.currentSelectedGameObject != null;
    }

    // Update is called once per frame
    void Update()
    {
        if (Input.GetKeyDown(KeyCode.Return))
        {
            SendObjective();
        }

        if (Input.GetKeyDown(KeyCode.T) && !UserTypingInput())
        {
            GameObject textObj = GameObject.FindWithTag(INPUT_FIELD_TAG);
            TMPro.TMP_InputField textMeshPro = textObj.GetComponent<TMPro.TMP_InputField>();
            textMeshPro.Select();
        }

        if (Input.GetKeyDown(KeyCode.N) && !UserTypingInput())
        {
            Network.NetworkManager.TaggedInstance().TransmitTurnComplete();
        }

        // Live feedback keyboard combos.
        if (Input.GetKeyDown(KeyCode.G) || Input.GetKeyDown(KeyCode.Alpha9)) {
            SendPositiveFeedback();
        }
        if (Input.GetKeyDown(KeyCode.B) || Input.GetKeyDown(KeyCode.Alpha0)) {
            SendNegativeFeedback();
        }

        if (Input.GetKeyDown(KeyCode.P))
        {
            DisplayCoordinates instance = DisplayCoordinates.GetInstance();
            if (instance != null)
            {
                instance.ToggleDisplay();
            }
        }
    }
}
