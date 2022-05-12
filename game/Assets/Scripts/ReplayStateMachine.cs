using System;
using System.Collections.Generic;
using UnityEngine;


public class ReplayStateMachine
{
    private bool _started = false;
    private DateTime _gameBegin = DateTime.MinValue;
    private int _messageFromIndex = 0;
    private int _turn = 0;

    private int _numberOfTurns = 0;

    private Network.MessageFromServer[] _messagesFromServer;
    private Dictionary<int, int> _turnIndexMap;
    private Network.NetworkRouter _replayRouter;

    private bool _fastForward = false;

    public bool Started()
    {
        return _started;
    }
    public void Start()
    {
        _started = true;
        NextTurn();
    }

    public void NextTurn()
    {
        if (_turn >= _numberOfTurns) return;
        _turn++;
    }

    public void PreviousTurn()
    {
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
                return;
            }
            while ((_messageFromIndex < _turnIndexMap[_turn]) && (_messageFromIndex < _messagesFromServer.Length))
            {
                // Unexpire actions, unless we're in FF mode. Then set them to expire immediately.
                if (_messagesFromServer[_messageFromIndex].actions != null)
                {
                    foreach(Network.Action action in _messagesFromServer[_messageFromIndex].actions)
                    {
                        if (_fastForward) {
                            action.expiration = DateTime.Now.ToString("o");
                            continue;
                        }
                        action.expiration = DateTime.Now.AddSeconds(10).ToString("o");
                    }
                }
                _replayRouter.HandleMessage(_messagesFromServer[_messageFromIndex]);
                _messageFromIndex++;
            }
            _fastForward = false;
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
        DateTime fromServerStart = DateTime.Parse(_messagesFromServer[firstTimestampedIndex].transmit_time, null, System.Globalization.DateTimeStyles.RoundtripKind);
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