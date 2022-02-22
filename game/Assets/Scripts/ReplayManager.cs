using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.Networking;
using Newtonsoft.Json;

public class ReplayManager : MonoBehaviour
{
    public static readonly string GAME_ID_PARAM = "game_id";
    public static readonly string ESCAPE_MENU_REPLAY_INFO_TAG = "ESCAPE_MENU_REPLAY_INFO";
    public static readonly string REPLAY_TURN = "REPLAY_TURN";
    private Network.MessageFromServer[] _messagesFromServer;
    private ReplayStateMachine _replayStateMachine;
    private bool _requestFailed = false;
    private bool _dataDownloaded = false;
    private DateTime _lastDownloadAttempt = DateTime.MinValue;

    private DateTime _lastInfoUpdate = DateTime.MinValue;
    private Network.GameInfo _gameInfo;


    public bool TestMode = false;
    public int TestModeId = 230;

    private Logger _logger;

    void Awake()
    {
        _logger = Logger.GetOrCreateTrackedLogger("ReplayManager");
        Network.NetworkManager.TaggedInstance().InjectReplayRole(Network.Role.LEADER);
    }

    void Start()
    {
        _replayStateMachine = new ReplayStateMachine();
        StartCoroutine(DownloadGameLogsFromServer());
    }

    string ReplayStatusInfo()
    {
        if (_gameInfo == null)
            return "";
        return string.Format("Game name: {0}\nID: {1}\nStart Time: {2}", _gameInfo.game_name, _gameInfo.game_id, _gameInfo.start_time);
    }

    void Update()
    {
        // Call NextTurn() and PreviousTurn() when the user presses the left and right arrow keys.
        if (Input.GetKeyDown(KeyCode.LeftArrow))
        {
            PreviousTurn();
        }
        if (Input.GetKeyDown(KeyCode.RightArrow))
        {
            NextTurn();
        }

        if (_replayStateMachine.Started()){
            _replayStateMachine.Update();
        }
        if ((DateTime.Now - _lastInfoUpdate).Seconds > 5)
        {
            GameObject obj = GameObject.FindGameObjectWithTag(ESCAPE_MENU_REPLAY_INFO_TAG);
            if (obj != null)
            {
                TMPro.TMP_Text textMeshPro = obj.GetComponent<TMPro.TMP_Text>();
                textMeshPro.text = ReplayStatusInfo();
            }
        }
        if (_messagesFromServer != null && _dataDownloaded && !_requestFailed && !_replayStateMachine.Started())
        {
            _replayStateMachine.Load(_messagesFromServer);
            _replayStateMachine.Start();
            SetTurnDisplay();
        }
        if (_requestFailed && ((DateTime.Now - _lastDownloadAttempt).Seconds > 5))
        {
            _dataDownloaded = false;
            _requestFailed = false;
            StartCoroutine(DownloadGameLogsFromServer());
        }
    }

    public void SetTurnDisplay()
    {
        GameObject obj = GameObject.FindGameObjectWithTag(REPLAY_TURN);
        if (obj != null)
        {
            Text text = obj.GetComponent<Text>();
            text.text = string.Format("{0} / {1}", _replayStateMachine.Turn(), _replayStateMachine.TotalTurns());
        }
    }

    public void PreviousTurn()
    {
        _replayStateMachine.PreviousTurn();
        SetTurnDisplay();
    }

    public void NextTurn()
    {
        _replayStateMachine.NextTurn();
        SetTurnDisplay();
    }

    public void Reset()
    {
        _replayStateMachine.Reset();
        SetTurnDisplay();
    }

    public void ProcessGameLog(Network.GameLog log)
    {
        Network.NetworkManager.TaggedInstance().InjectReplayConfig(log.server_config);
        _gameInfo = log.game_info;
        // Find the leader ID.
        int leader_id = -1;
        for (int i = 0; i < log.game_info.roles.Count; ++i)
        {
            if (log.game_info.roles[i] == Network.Role.LEADER)
            {
                leader_id = log.game_info.ids[i];
                break;
            }
        }
        if (leader_id == -1)
        {
            Debug.Log("Error finding leader ID.");
            _requestFailed = true;
            return;
        }
        List<Network.LogEntry> leaderLogEntries = new List<Network.LogEntry>();
        for (int i = 0; i < log.log_entries.Count; ++i)
        {
            if (log.log_entries[i].player_id == leader_id)
            {
                leaderLogEntries.Add(log.log_entries[i]);
            }
        }
        _messagesFromServer = new Network.MessageFromServer[leaderLogEntries.Count];
        for (int i = 0; i < leaderLogEntries.Count; ++i)
        {
            if (leaderLogEntries[i].message_direction != Network.Direction.FROM_SERVER)
            {
                Debug.Log("ERR: Encountered MessageToServer in game log!");
                _requestFailed = true;
                return;
            }
            _messagesFromServer[i] = leaderLogEntries[i].message_from_server;
        }
        _dataDownloaded = true;
    }

    private IEnumerator DownloadGameLogsFromServer()
    {
        _lastDownloadAttempt = DateTime.Now;
        string url = Network.NetworkManager.BaseUrl(/*websocket=*/false) + "data/game_logs/" + GameId();
        _logger.Info("Downloading game logs from " + url);
        using (UnityWebRequest webRequest = UnityWebRequest.Get(url))
        {
            // Request and wait for the desired page.
            yield return webRequest.SendWebRequest();

            switch (webRequest.result)
            {
                case UnityWebRequest.Result.ConnectionError:
                case UnityWebRequest.Result.DataProcessingError:
                    Debug.LogError("Error: " + webRequest.error);
                    _requestFailed = true;
                    break;
                case UnityWebRequest.Result.ProtocolError:
                    Debug.LogError("HTTP Error: " + webRequest.error);
                    _requestFailed = true;
                    break;
                case UnityWebRequest.Result.Success:
                    Debug.Log("Received: " + webRequest.downloadHandler.text);
                    Debug.Log(webRequest.downloadHandler);
                    string data = webRequest.downloadHandler.text;
                    Network.GameLog log = JsonConvert.DeserializeObject<Network.GameLog>(data);
                    ProcessGameLog(log);
                    break;
                default:
                    Debug.LogError("Unknown Error: " + webRequest.error);
                    _requestFailed = true;
                    break;
            }
        }

    }

    private int GameId()
    {
        // Allow a hardcoded test ID to be injected for testing.
        if (TestMode && (Application.platform != RuntimePlatform.WebGLPlayer))
        {
            return TestModeId;
        }
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
        _logger.Info("Game ID: " + gameId);
        return gameId;
    }

}
