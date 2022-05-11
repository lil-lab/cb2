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
        NextTurn();
    }

    public void NextTurn()
    {
        if (_turn >= _messagesFromServer.Length) return;
        _turn++;
    }

    public void PreviousTurn()
    {
        if (_turn <= 0) return;
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
        if (_messageFromIndex < 0)
        {
            _messageFromIndex = 0;
        }
        if (_messageFromIndex < _messagesFromServer.Length)
        {
            if (!_turnIndexMap.ContainsKey(_turn))
            {
                Debug.Log("Turn " + _turn + " not found.");
                foreach (int key in _turnIndexMap.Keys)
                {
                    Debug.Log("Key: " + key);
                }
                return;
            }
            while ((_messageFromIndex < _turnIndexMap[_turn]) && (_messageFromIndex < _messagesFromServer.Length))
            {
                // Unexpire the message.
                foreach(Network.Action action in _messagesFromServer[_messageFromIndex].Actions)
                {
                    action.Expiration = DateTime.Now.AddSeconds(10).ToString("o");
                }
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
                    _turnIndexMap[turn] = i;
                }
            }
        }
        _turnIndexMap[turn + 1] = _messagesFromServer.Length;
        _turn = 0;
        return Util.Status.OkStatus();
    }
}