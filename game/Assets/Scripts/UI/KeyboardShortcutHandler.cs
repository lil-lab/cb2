using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

public class KeyboardShortcutHandler : MonoBehaviour
{
    private static readonly string INPUT_FIELD_TAG = "MessageInputField";

    public void SendPositiveFeedback()
    {
        Network.LiveFeedback feedback = new Network.LiveFeedback();
        feedback.signal = Network.FeedbackType.POSITIVE;
        Network.NetworkManager.TaggedInstance().TransmitLiveFeedback(feedback);
    }

    public void SendNegativeFeedback()
    {
        Network.LiveFeedback feedback = new Network.LiveFeedback();
        feedback.signal = Network.FeedbackType.NEGATIVE;
        Network.NetworkManager.TaggedInstance().TransmitLiveFeedback(feedback);
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
        if (Input.GetKey(KeyCode.G)) {
            SendPositiveFeedback();
        }
        if (Input.GetKey(KeyCode.B)) {
            SendNegativeFeedback();
        }
    }
}
