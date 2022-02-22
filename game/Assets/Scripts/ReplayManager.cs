using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using Newtonsoft.Json;

public class ReplayManager : MonoBehaviour
{
    public static string GAME_ID_PARAM = "game_id";
    private Network.MessageFromServer[] _messagesFromServer;
    private Network.MessageToServer[] _messagesToServer;
    private ReplayStateMachine _replayStateMachine;
    private bool _requestFailed = false;
    private bool _dataDownloaded = false;
    private bool _messagesLoaded = false;

    void Start()
    {
        StartCoroutine(DownloadMessagesFromServer());
        StartCoroutine(DownloadMessagesToServer());
    }

    void Update()
    {
        if (_messagesToServer != null && _messagesFromServer != null && !_requestFailed && !_replayStateMachine.Started())
        {
            _replayStateMachine.Load(_messagesFromServer, _messagesToServer);
            _replayStateMachine.Start();
        }
        if (_replayStateMachine.Started()){
            _replayStateMachine.Update();
        }
    }

    private IEnumerator DownloadMessagesToServer()
    {
        string url = Network.NetworkManager.BaseUrl();
        UnityWebRequest www = new UnityWebRequest(url + "data/messages_to_server/" + GameId());
        yield return www.SendWebRequest();

        if (www.result != UnityWebRequest.Result.Success)
        {
            Debug.Log("Error downloading data.");
            _requestFailed = true;
            yield break;
        }

        string data = www.downloadHandler.text;
        string[] lines = data.Split('\n');
        _messagesToServer = new Network.MessageToServer[lines.Length];
        for (int i = 0; i < lines.Length; ++i) 
        {
            _messagesToServer[i] = JsonConvert.DeserializeObject<Network.MessageToServer>(lines[i]);
        }
    }

    private IEnumerator DownloadMessagesFromServer()
    {
        string url = Network.NetworkManager.BaseUrl();
        UnityWebRequest www = new UnityWebRequest(url + "data/messages_from_server/" + GameId());
        yield return www.SendWebRequest();

        if (www.result != UnityWebRequest.Result.Success)
        {
            Debug.Log("Error downloading data.");
            _requestFailed = true;
            yield break;
        }

        string data = www.downloadHandler.text;
        string[] lines = data.Split('\n');
        _messagesFromServer = new Network.MessageFromServer[lines.Length];
        for (int i = 0; i < lines.Length; ++i) 
        {
            _messagesFromServer[i] = JsonConvert.DeserializeObject<Network.MessageFromServer>(lines[i]);
        }
    }

    private int GameId()
    {
        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        if (!urlParameters.ContainsKey(GAME_ID_PARAM))
        {
            return -1;
        }
        string gameIdValue = urlParameters[GAME_ID_PARAM];
        if (!int.TryParse(gameIdValue, out int gameId)) 
        {
            return -1;
        }
        return gameId;
    }

}
