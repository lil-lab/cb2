using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class DisplayLobbyName : MonoBehaviour
{
    // Start is called before the first frame update
    void Start()
    {
        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        if (!urlParameters.ContainsKey("lobby_name"))
        {
            // Disable the parent panel if there is no lobby name.
            gameObject.transform.parent.gameObject.SetActive(false);
            return;
        }
        // Display the lobby name to the user.
        gameObject.GetComponent<TMPro.TMP_Text>().text = "In Lobby " + urlParameters["lobby_name"];
        gameObject.SetActive(true);
    }
}
