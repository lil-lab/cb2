using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Network
{
    public class NetworkManager : MonoBehaviour
    {
        public static string TAG = "NetworkManager";

        public string URL = "ws://localhost:8080/player_endpoint";

        private ClientConnection _client;
        private NetworkMapSource _networkMapSource;
        private NetworkRouter _router;
        private ActorManager _actorManager;
        private Player _player;
        private DateTime _lastReconnect;

        public NetworkMapSource MapSource()
        {
            if (_networkMapSource == null)
            {
                Debug.Log("Retrieved map source before it was initialized."); 
	        }
            return _networkMapSource; 
	    }

        public void TransmitAction(ActionQueue.IAction action)
        {
            _router.TransmitAction(action);
        }

        public void Awake()
        {
            gameObject.tag = TAG;
            _networkMapSource = new NetworkMapSource();

            GameObject obj = GameObject.FindGameObjectWithTag(ActorManager.TAG);
            _actorManager = obj.GetComponent<ActorManager>();
            if (_actorManager == null)
            {
                Debug.LogError("Could not initialize ActorManager via tag: " + ActorManager.TAG);
	        }

            GameObject playerObj = GameObject.FindGameObjectWithTag(Player.TAG);
            _player = playerObj.GetComponent<Player>();

            if (_player == null)
            {
                Debug.LogError("Could not initialize Player via tag: " + Player.TAG);
	        }

            string url = URL;
            if (Application.absoluteURL != "")
            {
                // We can figure out the server's address based on Unity's API.
                Uri servedUrl = new Uri(Application.absoluteURL);
                UriBuilder endpointUrlBuilder =
		            new UriBuilder("ws", servedUrl.Host, servedUrl.Port,
		                           "/player_endpoint");
                url = endpointUrlBuilder.Uri.AbsoluteUri;
	        }
            Debug.Log("Using url: " + url);
            _client = new ClientConnection(url);
            _router = new NetworkRouter(_client, _networkMapSource, _actorManager, _player);

            _lastReconnect = DateTime.Now;
        }

        // Start is called before the first frame update
        private void Start()
        {
            _client.Start();
        }

        public void Reconnect()
        {
            _client.Reconnect();
	    }

        // Update is called once per frame
        void Update()
        {
            if (_client.IsClosed() && ((DateTime.Now - _lastReconnect).Seconds > 3))
            {
                Invoke("Reconnect", 3);
                _lastReconnect = DateTime.Now;
	        }
            _client.Update();
        }
    }
}
