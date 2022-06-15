using System;
using System.Collections.Generic;
using UnityEngine;


public class ReplayStateMachine
{
    public enum PlaybackMode {
        NONE = 0,
        STEP_THROUGH = 1,
        PLAY = 2
    }

    private bool _started = false;
    private DateTime _gameBegin = DateTime.MinValue;
    private int _messageFromIndex = 0;
    private int _turn = 0;

    private PlaybackMode _mode;

    private Logger _logger;

    private int _numberOfTurns = 0;

    DateTime _lastMessageWallTime;
    float _playbackSpeed;

    private Network.MessageFromServer[] _messagesFromServer;
    private Dictionary<int, int> _turnIndexMap;
    private Network.NetworkRouter _replayRouter;

    private bool _fastForward = false;

    public ReplayStateMachine()
    {
        _logger = Logger.GetOrCreateTrackedLogger("ReplayStateMachine");
    }

    public bool Started()
    {
        return _started;
    }
    public void Start()
    {
        _playbackSpeed = 1.0f;
        _mode = PlaybackMode.STEP_THROUGH;
        _started = true;
        NextTurn();
        _lastMessageWallTime = DateTime.MinValue;
    }

    public PlaybackMode PlayMode()
    {
        return _mode;
    }

    public void Play()
    {
        _mode = PlaybackMode.PLAY;
    }

    public float Speed()
    {
        return _playbackSpeed;
    }

    public void SetSpeed(float speed)
    {
        _playbackSpeed = speed;
    }

    public void Pause()
    {
        _mode = PlaybackMode.STEP_THROUGH;
        // Fast-forward to the end of the current turn before pausing.
        _fastForward = true;
    }

    public void NextTurn()
    {
        _mode = PlaybackMode.STEP_THROUGH;
        if (_turn >= _numberOfTurns) return;
        _turn++;
    }

    public void PreviousTurn()
    {
        _mode = PlaybackMode.STEP_THROUGH;
        if (_turn <= 1) return;
        _fastForward = true;
        SetTurn(_turn - 1);
    }

    public void SetTurn(int turn)
    {
        if (turn >= _turn)
        {
            _turn = turn;
        } else 
        {
            Reset();
            _turn = turn;
        }
    }

    public int Turn()
    {
        return _turn;
    }

    public int TotalTurns()
    {
        return _numberOfTurns;
    }

    public void Reset()
    {
        _messageFromIndex = 0;
        _turn = 0;
    }

    private DateTime ParseTimestamp(string timestamp_str)
    {
        return DateTime.Parse(timestamp_str, null, System.Globalization.DateTimeStyles.RoundtripKind);
    }

    public bool TimeForNextPacket()
    {
        DateTime nextTransmitTime = ParseTimestamp(_messagesFromServer[_messageFromIndex].transmit_time);
        DateTime lastTransmitTime = (_messageFromIndex > 0) ? ParseTimestamp(_messagesFromServer[_messageFromIndex - 1].transmit_time) : DateTime.MinValue;
        float gameTimeDurationMillis = (float) (nextTransmitTime.Subtract(lastTransmitTime)).TotalMilliseconds;
        float wallTimeMillis = (float) (DateTime.Now.Subtract(_lastMessageWallTime)).TotalMilliseconds;
        return (wallTimeMillis * _playbackSpeed >= gameTimeDurationMillis);
    }

    public void AdvanceMessage()
    {
        if ((_messageFromIndex < _turnIndexMap[_turn]) && (_messageFromIndex < _messagesFromServer.Length) && (TimeForNextPacket() || _fastForward))
        {
            // Unexpire actions, unless we're in FF mode. Then set them to expire immediately.
            if (_messagesFromServer[_messageFromIndex].actions != null)
            {
                foreach(Network.Action action in _messagesFromServer[_messageFromIndex].actions)
                {
                    if (_fastForward) {
                        action.expiration = DateTime.Now.ToString("o");
                        action.duration_s = 0.0001f;
                        continue;
                    }
                    action.expiration = DateTime.Now.AddSeconds(10).ToString("o");
                    // Adjust action duration to match playback speed.
                    if (_playbackSpeed != 0)
                        action.duration_s /= _playbackSpeed;
                }
            }
            _logger.Info("Replaying message. Timestamp: " + _messagesFromServer[_messageFromIndex].transmit_time + ", index: " + _messageFromIndex);
            _replayRouter.HandleMessage(_messagesFromServer[_messageFromIndex]);
            _lastMessageWallTime = DateTime.Now;
            _messageFromIndex++;
        } else {
            if ((_messageFromIndex >= _turnIndexMap[_turn]) && _fastForward)
            {
                _logger.Info("Reached end of turn " + _turn + ".");
                _fastForward = false;
            }
            if ((_mode == PlaybackMode.PLAY) && (_turn < _numberOfTurns) && (_messageFromIndex >= _turnIndexMap[_turn]))
            {
                // Advance play if speed > 0.
                _turn++;
            }
        }
    }

    public void CatchUpFastForward()
    {
        while (_fastForward)
        {
            AdvanceMessage();
        }
    }

    public void Update()
    {
        if (_messageFromIndex < 0)
        {
            _messageFromIndex = 0;
        }
        if (_messageFromIndex < _messagesFromServer.Length)
        {
            if (!_turnIndexMap.ContainsKey(_turn))
            {
                _logger.Warn("Turn " + _turn + " not found in turn index map.");
                return;
            }
            if (_fastForward) {
                CatchUpFastForward();
            } else {
                AdvanceMessage();
            }
        }
    }

    public Util.Status Load(Network.MessageFromServer[] messagesFromServer)
    {
        _messagesFromServer = messagesFromServer;

        GameObject obj = GameObject.FindGameObjectWithTag(EntityManager.TAG);
        if (obj == null)
        {
            return Util.Status.NotFound("Could not find tag: " + EntityManager.TAG);
        }
        EntityManager entityManager = obj.GetComponent<EntityManager>();
        if (entityManager == null)
        {
            return Util.Status.NotFound("Could not find component: " + EntityManager.TAG);
        }

        _replayRouter = new Network.NetworkRouter(null, Network.NetworkManager.TaggedInstance().NetworkMapSource(), Network.NetworkManager.TaggedInstance(), entityManager, null, Network.NetworkRouter.Mode.REPLAY);
        GameObject playerObj = GameObject.FindGameObjectWithTag(Player.TAG);
        if (playerObj != null)
        {
            _replayRouter.SetPlayer(playerObj.GetComponent<Player>());
        }

        // Calculate the time of the first message.
        int firstTimestampedIndex = 0;
        while (firstTimestampedIndex < _messagesFromServer.Length && _messagesFromServer[firstTimestampedIndex].transmit_time == null)
        {
            firstTimestampedIndex++;
        }
        DateTime fromServerStart = ParseTimestamp(_messagesFromServer[firstTimestampedIndex].transmit_time);
        _gameBegin = fromServerStart;

        _turnIndexMap = new Dictionary<int, int>();

        // The first turn starts with the first action message.
        for (int i = 0; i < _messagesFromServer.Length; i++)
        {
            if (_messagesFromServer[i].actions != null)
            {
                _turnIndexMap[0] = i;
                break;
            }
        }
        Network.Role currentTurnRole = Network.Role.NONE;
        int turnNumber = 0;
        for (int i = 0; i < _messagesFromServer.Length; ++i)
        {
            if (_messagesFromServer[i].type == Network.MessageFromServer.MessageType.TURN_STATE)
            {
                if (_messagesFromServer[i].turn_state.turn != currentTurnRole) {
                    turnNumber++;
                    _turnIndexMap[turnNumber] = i;
                    currentTurnRole = _messagesFromServer[i].turn_state.turn;
                }
            }
        }
        _turnIndexMap[turnNumber + 1] = _messagesFromServer.Length;
        _numberOfTurns = turnNumber;
        _turn = 0;
        return Util.Status.OkStatus();
    }
}