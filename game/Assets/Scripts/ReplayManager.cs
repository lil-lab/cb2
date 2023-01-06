using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.Networking;

public class ReplayManager : MonoBehaviour
{
    public static readonly string TAG = "ReplayManager";
    public static readonly string GAME_ID_PARAM = "game_id";
    public static readonly string ESCAPE_MENU_REPLAY_INFO_TAG = "ESCAPE_MENU_REPLAY_INFO";
    public static readonly string REPLAY_TURN = "REPLAY_TURN";
    private Logger _logger;

    private Network.ReplayInfo _gameInfo;

    void Awake()
    {
        _logger = Logger.GetOrCreateTrackedLogger("ReplayManager");
        Network.NetworkManager.TaggedInstance().InjectReplayRole(Network.Role.LEADER);
    }

    void Start()
    {
        // Get the game ID from the URL.
        var urlParams = Network.NetworkManager.UrlParameters();
        if (!urlParams.ContainsKey(GAME_ID_PARAM))
        {
            _logger.Info("No game ID found in URL parameters.");
            return;
        }
        // Send a replay start request to the server.
        Network.ReplayRequest request = new Network.ReplayRequest();
        request.type = Network.ReplayRequestType.START_REPLAY;
        request.game_id = int.Parse(urlParams[GAME_ID_PARAM]);
        Network.NetworkManager.TaggedInstance().TransmitReplayMessage(request);

        // Btw, NetworkRouter needs to be set to REPLAY mode to correctly handle
        // messages during replay vs during a normal game. But this is handled
        // in NetworkManager for us via OnSceneLoaded(). That way, it also can
        // handle disabling replay mode when we leave the replay scene.
    }

    public static ReplayManager TaggedInstance()
    {
        GameObject replayObj = GameObject.FindGameObjectWithTag(TAG);
        if (replayObj == null)
            return null;
        return replayObj.GetComponent<ReplayManager>();
    }

    public void HandleReplayResponse(Network.ReplayResponse response)
    {
        if (response.type == Network.ReplayResponseType.REPLAY_STARTED)
        {
            _logger.Info("Replay started.");
        }
        else if (response.type == Network.ReplayResponseType.REPLAY_INFO)
        {
            HandleReplayInfo(response.info);
        }
    }

    public void HandleReplayInfo(Network.ReplayInfo info)
    {
        _gameInfo = info;
        if (_gameInfo == null)
        {
            _logger.Info("Replay info is still null.");
            return;
        }
        SetTurnDisplay();
    }

    string ReplayStatusInfo()
    {
        if (_gameInfo == null)
            return "";
        return string.Format("Game id: {0}\nID: {1}\nStart Time: {2}\nTick: {3}", _gameInfo.game_id, _gameInfo.start_time, _gameInfo.tick);
    }

    public void UpdateEscapeMenuText()
    {
        GameObject obj = GameObject.FindGameObjectWithTag(ESCAPE_MENU_REPLAY_INFO_TAG);
        if (obj != null)
        {
            Text text = obj.GetComponent<Text>();
            text.text = ReplayStatusInfo();
        }
    }

    void Update()
    {
        SetTurnDisplay();

        // Call NextTurn() and PreviousTurn() when the user presses the left and right arrow keys.
        if (Input.GetKeyDown(KeyCode.LeftArrow))
        {
            PreviousTurn();
        }
        if (Input.GetKeyDown(KeyCode.RightArrow))
        {
            NextTurn();
        }
    }

    public void SetTurnDisplay()
    {
        GameObject obj = GameObject.FindGameObjectWithTag(REPLAY_TURN);
        if (obj != null)
        {
            Text text = obj.GetComponent<Text>();
            text.text = string.Format("{0} / {1}", _gameInfo.turn, _gameInfo.total_turns);
        }
        if (_gameInfo.paused)
        {
            SetPlayButtonText("Play");
        } else {
            SetPlayButtonText("Pause");
        }
    }

    public void PreviousTurn()
    {
        _logger.Info("PreviousTurn");
        Network.ReplayRequest request = new Network.ReplayRequest();
        request.type = Network.ReplayRequestType.REPLAY_COMMAND;
        request.command = Network.ReplayCommand.PREVIOUS;
        Network.NetworkManager.TaggedInstance().TransmitReplayMessage(request);
        SetPlayButtonText("Play");
    }

    public void NextTurn()
    {
        _logger.Info("NextTurn");
        Network.ReplayRequest request = new Network.ReplayRequest();
        request.type = Network.ReplayRequestType.REPLAY_COMMAND;
        request.command = Network.ReplayCommand.NEXT;
        Network.NetworkManager.TaggedInstance().TransmitReplayMessage(request);
        SetPlayButtonText("Play");
    }

    public void Reset()
    {
        _logger.Info("Reset");
        Network.ReplayRequest request = new Network.ReplayRequest();
        request.type = Network.ReplayRequestType.REPLAY_COMMAND;
        request.command = Network.ReplayCommand.RESET;
        Network.NetworkManager.TaggedInstance().TransmitReplayMessage(request);
        SetPlayButtonText("Play");
    }

    private void SetPlayButtonText(string text)
    {
        GameObject button_obj = GameObject.FindGameObjectWithTag("PLAYPAUSE");
        if (button_obj == null)
        {
            _logger.Warn("No play/pause button found.");
            return;
        }
        Button button = button_obj.GetComponent<Button>();
        button.GetComponentInChildren<Text>().text = text;
    }

    public void PlayPause()
    {
        if (_gameInfo == null)
        {
            _logger.Warn("No game info yet. Ignoring PlayPause request.");
            return;
        }
        if (!_gameInfo.paused)
        {
            _logger.Info("Pausing...");
            Network.ReplayRequest request = new Network.ReplayRequest();
            request.type = Network.ReplayRequestType.REPLAY_COMMAND;
            request.command = Network.ReplayCommand.PAUSE;
            Network.NetworkManager.TaggedInstance().TransmitReplayMessage(request);
        } else {
            _logger.Info("Playing...");
            Network.ReplayRequest request = new Network.ReplayRequest();
            request.type = Network.ReplayRequestType.REPLAY_COMMAND;
            request.command = Network.ReplayCommand.PLAY;
            Network.NetworkManager.TaggedInstance().TransmitReplayMessage(request);
        }
    }

    public void SetSpeed(float speed)
    {
        _logger.Info("SetSpeed " + speed);
        Network.ReplayRequest request = new Network.ReplayRequest();
        request.type = Network.ReplayRequestType.REPLAY_COMMAND;
        request.command = Network.ReplayCommand.REPLAY_SPEED;
        request.replay_speed = speed;
        Network.NetworkManager.TaggedInstance().TransmitReplayMessage(request);
    }
}
