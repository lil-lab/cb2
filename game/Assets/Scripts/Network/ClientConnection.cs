using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using NativeWebSocket;
using Newtonsoft.Json;
using UnityEngine;

namespace Network
{

    public class ClientConnection
    {
        private WebSocket _webSocket;
        public string _url;
        private bool _autoReconnect;
        private NetworkRouter _router;
        private ConcurrentQueue<Network.MessageToServer> _messageQueue;
        private DateTime _lastReconnect;
        private Logger _logger;

        string fix_json(string value)
        {
            value = "{\"Items\":" + value + "}";
            return value;
        }

        public ClientConnection(string url, bool autoReconnect=false)
        {
            _logger = Logger.CreateTrackedLogger("ClientConnection");
            _url = url;
            _messageQueue = new ConcurrentQueue<Network.MessageToServer>();
            _autoReconnect = autoReconnect;
            _lastReconnect = DateTime.Now;
        }

        public void RegisterHandler(NetworkRouter router)
        {
            _router = router;
        }

        public bool IsClosed()
        {
            return _webSocket.State.HasFlag(WebSocketState.Closed);
        }

        public bool IsConnected()
        {
            return _webSocket.State.HasFlag(WebSocketState.Open);
        }
        public bool IsConnecting()
        {
            return _webSocket.State.HasFlag(WebSocketState.Connecting);
        }

        public bool IsClosing()
        {
            return _webSocket.State.HasFlag(WebSocketState.Closing);
        }

        public void TransmitMessage(MessageToServer message)
        {
            _logger.Info("Sending message of type: " + message.type.ToString());
            _messageQueue.Enqueue(message);
        }

        private void OnOpen()
        {
            _logger.Info("Connection open!");
        }

        private void OnError(string e)
        {
            _logger.Info("Connection error: " + e);
        }

        private void OnClose(WebSocketCloseCode code)
        {
            _logger.Info("Connection closed: " + code);
            _webSocket.OnOpen -= OnOpen;
            _webSocket.OnError -= OnError;
            _webSocket.OnClose -= OnClose;
            _webSocket.OnMessage -= OnMessage;

            // Quit the active game.
            NetworkManager.TaggedInstance().DisplayGameOverMenu("Lost connection to server.");
        }

        private void OnMessage(byte[] bytes)
        {
            if (_router == null)
            {
                return;
            }

            string received = System.Text.Encoding.UTF8.GetString(bytes);
            _logger.Info("[" + DateTime.Now.ToString() + "]: Received: " + received);
            MessageFromServer message = JsonConvert.DeserializeObject<MessageFromServer>(System.Text.Encoding.ASCII.GetString(bytes));
            _router.HandleMessage(message);
        }

        private async void Reconnect()
        {
            if (_webSocket != null)
            {
                _webSocket.OnOpen -= OnOpen;
                _webSocket.OnError -= OnError;
                _webSocket.OnClose -= OnClose;
                _webSocket.OnMessage -= OnMessage;
            }
            // Note: NativeWebSocket ignores headers in WEBGL builds.
            _webSocket = new WebSocket(_url, /*headers=*/null);
            _webSocket.OnOpen += OnOpen;
            _webSocket.OnError += OnError;
            _webSocket.OnClose += OnClose;
            _webSocket.OnMessage += OnMessage;

            _logger.Info("Connecting...");
            // waiting for messages
            await _webSocket.Connect();
            _lastReconnect = DateTime.Now;
        }

        // Start is called before the first frame update
        public void Start()
        {
            Reconnect();
        }

        public void Update()
        {

            if (_autoReconnect
                && IsClosed() 
                && ((DateTime.Now - _lastReconnect).Seconds > 3))
            {
                _logger.Info("Reconnecting...");
                Reconnect();
            }

            SendPendingActions();
#if !UNITY_WEBGL || UNITY_EDITOR
            if (_webSocket != null)
            {
                _webSocket.DispatchMessageQueue();
            }
#endif
        }

        private async void SendPendingActions()
        {
            if (_webSocket.State == WebSocketState.Open)
            {
                if (!_messageQueue.TryDequeue(out MessageToServer toServer))
                {
                    return;
                }

                if (toServer == null)
                {
                    _logger.Info("Dequeued a null MessageToServer.");
                    return;
                }

                _logger.Info("[" + DateTime.Now.ToString() + "]: Sending: " + JsonUtility.ToJson(toServer));
                await _webSocket.SendText(JsonUtility.ToJson(toServer));
            }
        }

        public async void OnApplicationQuit()
        {
            await _webSocket.Close();
        }

    }

}  // namespace Network