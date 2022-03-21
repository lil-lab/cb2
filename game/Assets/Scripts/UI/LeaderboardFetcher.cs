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
    [Serializable]
    class LeaderboardRecord
    {
        public string time;
        public int score;
        public string leader;
        public string follower;
    }

    private List<LeaderboardRecord> _board = null;
    private bool _leaderboardDisplayed = false;

    void Start()
    {
        StartCoroutine(GetLeaderboard());
    }

    void Update()
    {
        if (_board != null && !_leaderboardDisplayed)
        {
            string text = "Leaderboard: \n";
            // Convert the leaderboard to text, using a fixed-width encoding for each field.
            foreach (LeaderboardRecord record in _board)
            {
                text += string.Format("{0,10} {1,10} {2,15} {3,15}\n", record.time, record.score, record.leader, record.follower);
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
}
