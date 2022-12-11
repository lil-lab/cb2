using System;
using System.Collections;
using System.Collections.Generic;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.Networking;
using Newtonsoft.Json;

public class LeaderboardFetcher : MonoBehaviour
{
    public enum LobbyType
    {
        NONE = 0,
        MTURK,
        OPEN,
        GOOGLE,
        BOT
    }

    [Serializable]
    class LeaderboardRecord
    {
        public string time;
        public int score;
        public string leader;
        public string follower;
        public string lobby_name;
        public LobbyType lobby_type;
    }

    private List<LeaderboardRecord> _board = null;
    private Network.UserInfo _user_info = null;
    private bool _leaderboardDisplayed = false;

    void Start()
    {
        StartCoroutine(GetLeaderboard());
    }

    void Update()
    {
        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();
        if ((networkManager != null) && (networkManager.GetUserInfo() != null))
        {
            _user_info = networkManager.GetUserInfo();
        }
        if ((_board != null) && (_user_info != null) && !_leaderboardDisplayed)
        {
            string text = string.Format("Your username (auto-generated): {0, 15} and lobby type: {1, 15}\n", _user_info.user_name, _user_info.user_type);
            text += "Leaderboard: \n";
            text += string.Format("{0,10} {1,6} {2,23} {3,23} {4,15}\n", "Date", "Score", "Leader", "Follower", "Lobby Type");
            // Convert the leaderboard to text, using a fixed-width encoding for each field.
            foreach (LeaderboardRecord record in _board)
            {
                text += string.Format("{0,10} {1,6} {2,23} {3,23} {4, 15}\n", record.time, record.score, record.leader, record.follower, NameFromLobbyType(record.lobby_type));
            }
            GetComponent<Text>().text = text;
            _leaderboardDisplayed = true;
        }
    }

    IEnumerator GetLeaderboard()
    {
        string base_url = Network.NetworkManager.BaseUrl(/*websocket=*/false);
        using (UnityWebRequest webRequest = UnityWebRequest.Get(base_url + "data/leaderboard"))
        {
            // Request and wait for the desired page.
            yield return webRequest.SendWebRequest();

            switch (webRequest.result)
            {
                case UnityWebRequest.Result.ConnectionError:
                case UnityWebRequest.Result.DataProcessingError:
                    Debug.LogError("Error: " + webRequest.error);
                    break;
                case UnityWebRequest.Result.ProtocolError:
                    Debug.LogError("HTTP Error: " + webRequest.error);
                    break;
                case UnityWebRequest.Result.Success:
                    Debug.Log("Received: " + webRequest.downloadHandler.text);
                    _board = JsonConvert.DeserializeObject<List<LeaderboardRecord>>(webRequest.downloadHandler.text);
                    break;
            }
        }
    }

    private string NameFromLobbyType(LobbyType type)
    {
        switch (type)
        {
            case LobbyType.MTURK:
                return "MTurk";
            case LobbyType.OPEN:
                return "Open";
            case LobbyType.GOOGLE:
                return "Google";
            case LobbyType.BOT:
                return "Follower Pilot";
        }
        return "Unknown";
    }
}
