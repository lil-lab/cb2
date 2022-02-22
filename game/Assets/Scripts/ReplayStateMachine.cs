using System;

public class ReplayStateMachine {
    private bool _started = false;
    private bool _startTime = DateTime.MinValue;
    private bool _gameBegin = DateTime.MinValue;
    private int _messageFromIndex = 0;
    private int _messageToIndex = 0;
    private Network.MessagesFromServer _messagesFromServer;
    private Network.MessagesToServer _messagesToServer;
    private Network.NetworkRouter _replayRouter;

    public bool Started()
    {
        return _started;
        _startTime = DateTime.Now;
    }
    public void Start()
    {
        _started = true;
    }

    public void Update()
    {
        DateTime gameTime = _gameBegin + (DateTime.Now - _startTime);
        while (true)
        {
            if (_messageFromIndex < _messagesFromServer.Length)
            {
                if (_messagesFromServer[_messageFromIndex].TransmiTime < gameTime)
                {
                    _replayRouter.
                    _messageFromIndex++;
                }
            }
            if (_messageToIndex < _messagesToServer.Length)
            {

            }
        }
    }

    public void Load(Network.MessagesFromServer messagesFromServer, Network.MessagesToServer messagesToServer)
    {
        _messagesFromServer = messagesFromServer;
        _messagesToServer = messagesToServer;
        DateTime fromServerStart = DateTime.Parse(_messagesFromServer[0].TransmitTime, null, System.Globalization.DateTimeStyles.RoundtripKind);
        DateTime toServerStart = DateTime.Parse(_messagesToServer[0].TransmitTime, null, System.Globalization.DateTimeStyles.RoundtripKind);
        _gameBegin = (fromServer < toServer) ? fromServer : toServer;
    }
}