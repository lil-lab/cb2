using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class ButtonClickableOnTurn : MonoBehaviour
{
    public Network.Role Turn = Network.Role.LEADER;

    // Update is called once per frame
    void Update()
    {
        Network.NetworkManager network = Network.NetworkManager.TaggedInstance();
        if (network == null)
            return;
        if (network.IsReplay())
            return;
        Button b = gameObject.GetComponent<Button>();
        b.interactable = false;
        if (network.CurrentTurn() == Turn)
        {
            b.interactable = true;
        }
    }
}


