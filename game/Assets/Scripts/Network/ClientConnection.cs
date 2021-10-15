using UnityEngine;
using NativeWebSocket;
using System.Collections.Generic;
using System;
using System.Collections.Concurrent;

namespace Network
{

    public class ClientConnection : MonoBehaviour
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

        public ClientConnection(string url, NetworkRouter router)
        {
            _url = url;
            _router = router;
            _webSocket = new WebSocket(_url);
        }

        public void QueueForTransmission(int actorId, ActionQueue.IAction action)
        {
            Network.ActionType actionType;
            // TODO(sharf): We shouldn't have an aliasing between animation and action types. Clean this up later...
            switch(action.Info().Type)
            {
                case ActionQueue.AnimationType.INSTANT:
                    actionType = Network.ActionType.INSTANT;
                    break;
                case ActionQueue.AnimationType.TRANSLATE:
                    actionType = Network.ActionType.TRANSLATE;
                    break;
                case ActionQueue.AnimationType.WALKING:
                    actionType = Network.ActionType.TRANSLATE;
                    break;
                case ActionQueue.AnimationType.ROTATE:
                    actionType = Network.ActionType.ROTATE;
                    break;
                default:
                    Debug.Log("Unknown action type encountered. Defaulting to instant.");
                    actionType = Network.ActionType.INSTANT;
                    break;
	        }
            _actionQueue.Enqueue(new Network.Action()
            {
                ActorId = actorId,
                ActionType = actionType,
                AnimationType = (Network.AnimationType)action.Info().Type,
                Start = action.Info().Start,
                Destination = action.Info().Destination,
                StartHeading = action.Info().StartHeading,
                DestinationHeading = action.Info().DestinationHeading,
                DurationS = action.Info().DurationS,
                Expiration = action.Info().Expiration,
            });
	    }

        async void InitConnection()
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
                Invoke("InitConnection", 3);
            };

            _webSocket.OnMessage += (bytes) =>
            {
                 MessageFromServer message = JsonUtility.FromJson<MessageFromServer>(System.Text.Encoding.ASCII.GetString(bytes));
                _router.HandleMessage(message);
		    };

            // Keep sending messages at every 0.1s
            InvokeRepeating("SendWebSocketMessage", 0.0f, 0.1f);

            // waiting for messages
            await _webSocket.Connect();
        }

        // Start is called before the first frame update
        void Start()
        {
            InitConnection();
        }

        void Update()
        {
#if !UNITY_WEBGL || UNITY_EDITOR
            _webSocket.DispatchMessageQueue();
#endif
        }

        async void SendWebSocketMessage()
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

                MessageToServer toServer = new MessageToServer;

                toServer.Type = MessageToServer.MessageType.ACTIONS;
                toServer.Actions = actionsForServer;
                toServer.TransmitTime = DateTime.Now;
                await _webSocket.SendText(JsonUtility.ToJson(toServer));
            }
        }

        private async void OnApplicationQuit()
        {
            await _webSocket.Close();
        }

    }

}  // namespace Network