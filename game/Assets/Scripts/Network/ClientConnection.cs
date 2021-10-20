using UnityEngine;
using NativeWebSocket;
using System.Collections.Generic;
using System;
using System.Collections.Concurrent;
using Newtonsoft.Json;

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

        public void TransmitAction(int actorId, ActionQueue.IAction action)
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
                Expiration = action.Info().Expiration.ToString("o")
            }); ;
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
                Debug.Log(System.Text.Encoding.ASCII.GetString(bytes));
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
                await _webSocket.SendText(JsonUtility.ToJson(toServer));
            }
        }

        private async void OnApplicationQuit()
        {
            await _webSocket.Close();
        }

    }

}  // namespace Network