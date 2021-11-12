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
        private NetworkRouter _router;
        private ConcurrentQueue<Network.Action> _actionQueue;

        string fix_json(string value)
        {
            value = "{\"Items\":" + value + "}";
            return value;
        }

        public ClientConnection(string url)
        {
            _url = url;
            _webSocket = new WebSocket(_url);
            _actionQueue = new ConcurrentQueue<Network.Action>();
        }

        public void RegisterHandler(NetworkRouter router)
        {
            _router = router;
        }

        public bool IsClosed()
        {
            return _webSocket.State.HasFlag(WebSocketState.Closed);
        }

        public void TransmitAction(int id, ActionQueue.IAction action)
        {
            _actionQueue.Enqueue(action.Packet(id));
        }

        public async void Reconnect()
        {

            _webSocket.OnOpen += () =>
            {
                Debug.Log("Connection open!");
            };

            _webSocket.OnError += (e) =>
            {
                Debug.Log("Error! " + e);
            };

            _webSocket.OnClose += (e) =>
            {
                Debug.Log("Connection closed! Reconnecting...");
            };

            _webSocket.OnMessage += (bytes) =>
            {
                if (_router == null)
                {
                    return;
                }


                string received = System.Text.Encoding.ASCII.GetString(bytes);

                Debug.Log("Received: " + received);
                MessageFromServer message = JsonConvert.DeserializeObject<MessageFromServer>(System.Text.Encoding.ASCII.GetString(bytes));
                _router.HandleMessage(message);
            };

            // waiting for messages
            await _webSocket.Connect();
        }

        // Start is called before the first frame update
        public void Start()
        {
            Reconnect();
        }

        public void Update()
        {
            SendPendingActions();
#if !UNITY_WEBGL || UNITY_EDITOR
            _webSocket.DispatchMessageQueue();
#endif
        }

        private async void SendPendingActions()
        {
            if (_webSocket.State == WebSocketState.Open)
            {
                List<Action> actionsForServer = new List<Action>();
                Action action;
                while (_actionQueue.TryDequeue(out action))
                {
                    actionsForServer.Add(action);
                }

                if (actionsForServer.Count == 0)
                {
                    return;
                }

                MessageToServer toServer = new MessageToServer();

                toServer.Type = MessageToServer.MessageType.ACTIONS;
                toServer.Actions = actionsForServer;
                toServer.TransmitTime = DateTime.Now.ToString("o");
                Debug.Log("Sending: " + JsonUtility.ToJson(toServer));
                await _webSocket.SendText(JsonUtility.ToJson(toServer));
            }
        }

        private async void OnApplicationQuit()
        {
            await _webSocket.Close();
        }

    }

}  // namespace Network