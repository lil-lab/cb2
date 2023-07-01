using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class InteractableOnTurn : MonoBehaviour
{
    public Network.Role Turn = Network.Role.LEADER;

    private Network.Role _lastTurn = Network.Role.NONE;

    // Update is called once per frame
    void Update()
    {
        Network.NetworkManager network = Network.NetworkManager.TaggedInstance();
        if (network == null)
            return;
        if (network.IsReplay())
            return;
        if (network.CurrentTurn() == _lastTurn)
            return;
        _lastTurn = network.CurrentTurn();
        InputField input = gameObject.GetComponent<InputField>();
        TMPro.TMP_InputField tmpInput = gameObject.GetComponent<TMPro.TMP_InputField>();
        Button button = gameObject.GetComponent<Button>();
        if (input != null)
        {
            input.interactable = network.CurrentTurn() == Turn;
            return;
        }
        if (tmpInput != null)
        {
            tmpInput.interactable = network.CurrentTurn() == Turn;
            return;
        }
        if (button != null)
        {
            button.interactable = network.CurrentTurn() == Turn;
            return;
        }
        Debug.Log("Could not find an interactable field!!");
    }
}


