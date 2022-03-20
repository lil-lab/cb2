using System;
using System.Collections.Generic;
using UnityEngine;


public class ReplayStateMachine
{
    private bool _started = false;
    private DateTime _gameBegin = DateTime.MinValue;
    private int _messageFromIndex = 0;
    private int _turn = 0;
    private Network.MessageFromServer[] _messagesFromServer;
    private Dictionary<int, int> _turnIndexMap;
    private Network.NetworkRouter _replayRouter;

    public bool Started()
    {
        return _started;
    }
    public void Start()
    {
        _started = true;
    }

    public void NextTurn()
    {
        _turn++;
    }

    public void PreviousTurn()
    {
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

    public void Reset()
    {
        _messageFromIndex = 0;
        _turn = 0;
    }

    public void Update()
    {
        if (_messageFromIndex < _messagesFromServer.Length)
        {
            while ((_messageFromIndex < _turnIndexMap[_turn]) && (_messageFromIndex < _messagesFromServer.Length))
            {
                _replayRouter.HandleMessage(_messagesFromServer[_messageFromIndex]);
                _messageFromIndex++;
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

        // Calculate the time of the first message.
        DateTime fromServerStart = DateTime.Parse(_messagesFromServer[0].TransmitTime, null, System.Globalization.DateTimeStyles.RoundtripKind);
        _gameBegin = fromServerStart;

        _turnIndexMap = new Dictionary<int, int>();

        int turn = 0;
        _turnIndexMap[0] = 0;
        for (int i = 0; i < _messagesFromServer.Length; ++i)
        {
            if (_messagesFromServer[i].Type == Network.MessageFromServer.MessageType.TURN_STATE)
            {
                if (_messagesFromServer[i].TurnState.TurnNumber > turn) {
                    turn = _messagesFromServer[i].TurnState.TurnNumber;
                    _turnIndexMap[i] = turn;
                }
            }
        }
        _turnIndexMap[turn + 1] = _messagesFromServer.Length;
        return Util.Status.OkStatus();
    }
}