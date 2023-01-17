using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HideIfGoogle : MonoBehaviour
{
    void Start()
    {
        // True by default. False if all conditions are met.
        gameObject.SetActive(true);

        // Fetch server config.
        var config = Network.NetworkManager.TaggedInstance().ServerConfig();
        if (config == null)
        {
            Debug.LogError("No server config found.");
            return;
        }

        // Fetch URL parameters.
        var urlParameters = Network.NetworkManager.UrlParameters();
        if (urlParameters == null)
        {
            Debug.LogError("No URL parameters found.");
            return;
        }

        // Check the lobby name in the URL parameters and reference the config to determine if it's a scenario lobby.
        if (!urlParameters.ContainsKey("lobby_name"))
        {
            Debug.LogError("No lobby name URL parameter found.");
            return;
        }
        var lobbyName = urlParameters["lobby_name"];
        Network.LobbyType lobbyType = config.LobbyTypeFromName(lobbyName);
        gameObject.SetActive(lobbyType != Network.LobbyType.GOOGLE);
    }
}