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

        public NetworkMapSource MapSource()
        {
            if (_networkMapSource == null)
            {
                Debug.Log("Retrieved map source before it was initialized."); 
	        }
            return _networkMapSource; 
	    }

        public void SendAction(int actorId, ActionQueue.IAction action)
        {
            _client.QueueForTransmission(actorId, action);
        }

        public void Awake()
        {
            gameObject.tag = TAG;
            _networkMapSource = new NetworkMapSource();

            GameObject obj = GameObject.FindGameObjectWithTag(Actors.TAG);
            _actorManager = obj.GetComponent<Actors>().Manager();

            _router = new NetworkRouter(_networkMapSource, _actorManager);

            _client = new ClientConnection(URL, _router);
        }

        // Start is called before the first frame update
        private void Start()
        {
        }

        // Update is called once per frame
        void Update()
        {

        }
    }
}
