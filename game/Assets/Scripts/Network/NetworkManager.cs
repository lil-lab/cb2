using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;


namespace Network
{
    public class NetworkManager : MonoBehaviour
    {
        public static string TAG = "NetworkManager";

        public static NetworkManager Instance;

        public string URL = "ws://localhost:8080/player_endpoint";

        private ClientConnection _client;
        private NetworkMapSource _networkMapSource;
        private NetworkRouter _router;
        private EntityManager _entityManager;
        private Player _player;
        private DateTime _lastStatsPoll;
        private Role _role = Network.Role.NONE;
        private Role _currentTurn = Network.Role.NONE;

        public HexGridManager.IMapSource MapSource()
        {
            Scene scene = SceneManager.GetActiveScene();
            Debug.Log("[DEBUG] scene: " + scene.name);
            if (scene.name == "menu_scene")
            {
                Debug.Log("Loading menu map");
                return new FixedMapSource();
            }
            if (_networkMapSource == null)
            {
                Debug.Log("Retrieved map source before it was initialized.");
            }
            return _networkMapSource;
        }

        public static NetworkManager TaggedInstance()
        {
            GameObject obj = GameObject.FindGameObjectWithTag(Network.NetworkManager.TAG);
            if (obj == null)
                return null;
            return obj.GetComponent<Network.NetworkManager>();
        }

        public Role Role()
        {
            return _role;
        }

        public Role CurrentTurn()
        {
            return _currentTurn;
        }

        public void TransmitAction(ActionQueue.IAction action)
        {
            _router.TransmitAction(action);
        }

        public void TransmitTextMessage(string message)
        {
            MessageToServer toServer = new MessageToServer();
            toServer.TransmitTime = DateTime.Now.ToString("o");
            toServer.Type = MessageToServer.MessageType.TEXT;
            toServer.Message = new TextMessage();
            toServer.Message.Text = message;
            toServer.Message.Sender = _role;
            _client.TransmitMessage(toServer);
        }

        public void Awake()
        {
            gameObject.tag = TAG;
        }

        // Called when a user clicks the "Join Game" menu button. Starts a new game.
        public void JoinGame()
        {
            MessageToServer msg = new MessageToServer();
            msg.TransmitTime = DateTime.Now.ToString("o");
            msg.Type = MessageToServer.MessageType.ROOM_MANAGEMENT;
            msg.RoomRequest = new RoomManagementRequest();
            msg.RoomRequest.Type = RoomRequestType.JOIN;
            Debug.Log("[DEBUG]Joining game...");
            _client.TransmitMessage(msg);
        }

        // Pulls the player out of the wait queue to join a new game.
        public void CancelGameQueue()
        {
            MessageToServer msg = new MessageToServer();
            msg.TransmitTime = DateTime.Now.ToString("o");
            msg.Type = MessageToServer.MessageType.ROOM_MANAGEMENT;
            msg.RoomRequest = new RoomManagementRequest();
            msg.RoomRequest.Type = RoomRequestType.CANCEL;
            _client.TransmitMessage(msg);
        }

        public void QuitGame()
        {
            _networkMapSource.ClearMapUpdate();
            MessageToServer msg = new MessageToServer();
            msg.TransmitTime = DateTime.Now.ToString("o");
            msg.Type = MessageToServer.MessageType.ROOM_MANAGEMENT;
            msg.RoomRequest = new RoomManagementRequest();
            msg.RoomRequest.Type = RoomRequestType.LEAVE;
            _client.TransmitMessage(msg);
            Invoke("Reconnect", 0);
            SceneManager.LoadScene("menu_scene");
        }

        public Util.Status InitializeTaggedObjects()
        {
            GameObject obj = GameObject.FindGameObjectWithTag(EntityManager.TAG);
            if (obj == null)
            {
                _entityManager = null;
                return Util.Status.NotFound("Could not find tag: " + EntityManager.TAG);
            }
            _entityManager = obj.GetComponent<EntityManager>();
            if (_entityManager == null)
            {
                return Util.Status.NotFound("Could not find component: " + EntityManager.TAG);
            }

            GameObject playerObj = GameObject.FindGameObjectWithTag(Player.TAG);
            if (playerObj == null)
            {
                _player = null;
                return Util.Status.NotFound("Could not find tag: " + Player.TAG);
            }
            _player = playerObj.GetComponent<Player>();
            if (_player == null)
            {
                return Util.Status.NotFound("Could not find component: " + Player.TAG);
            }

            _router.SetEntityManager(_entityManager);
            _router.SetPlayer(_player);
            return Util.Status.OkStatus();
        }

        // Start is called before the first frame update
        private void Start()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(this);  // Persist network connection between scene changes.
            }
            else if (Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            _networkMapSource = new NetworkMapSource();

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
            _client = new ClientConnection(url, /*autoReconnect=*/ true);
            _router = new NetworkRouter(_client, _networkMapSource, this, null, null);

            Util.Status result = InitializeTaggedObjects();
            if (!result.Ok())
            {
                Debug.Log(result);
            }

            // Subscribe to new scene changes.
            SceneManager.sceneLoaded += OnSceneLoaded;


            _lastStatsPoll = DateTime.Now;
            _client.Start();
        }

        public void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            Util.Status result = InitializeTaggedObjects();
            if (!result.Ok())
            {
                Debug.Log(result);
            }
        }

        public void OnApplicationQuit()
        {
            _client.OnApplicationQuit();
        }

        public void Reconnect()
        {
            _client.Reconnect();
        }

        public void HandleRoomManagement(RoomManagementResponse response)
        {
            if (response.Type == RoomResponseType.JOIN_RESPONSE)
            {
                if (response.JoinResponse.Joined)
                {
                    Debug.Log("Joined room as " + response.JoinResponse.Role + "!");
                    SceneManager.LoadScene("game_scene");
                    _role = response.JoinResponse.Role;
                }
                else
                {
                    Debug.Log("Waiting for room. Position in queue: " + response.JoinResponse.PlaceInQueue);
                }
            }
            else if (response.Type == RoomResponseType.LEAVE_NOTICE)
            {
                Debug.Log("Kicked from game. Reason: " + response.LeaveNotice.Reason);
                SceneManager.LoadScene("menu_scene");
                _router.SetEntityManager(null);
                _router.SetPlayer(null);
            }
            else if (response.Type == RoomResponseType.STATS)
            {
                Debug.Log("Stats: " + response.Stats.ToString());
                GameObject obj = GameObject.FindGameObjectWithTag("Stats");
                if (obj == null) return;
                Text stats = obj.GetComponent<Text>();
                stats.text = "Players in game: " + response.Stats.PlayersInGame + "\n" +
                             "Games: " + response.Stats.NumberOfGames + "\n" +
                             "Followers Waiting: " + response.Stats.FollowersWaiting + "\n" +
                             "Leaders Waiting: " + response.Stats.LeadersWaiting + "\n";
            }
            else
            {
                Debug.Log("Received unknown room management response type: " + response.Type);
            }
        }

        public void HandleTurnState(TurnState state)
        {
            _currentTurn = state.Turn;
        }

        // Update is called once per frame
        void Update()
        {
            GameObject statsObj = GameObject.FindGameObjectWithTag("Stats");
            if (((DateTime.Now - _lastStatsPoll).Seconds > 1) && (statsObj != null) && (statsObj.activeInHierarchy))
            {
                Debug.Log("Requesting stats..");
                _lastStatsPoll = DateTime.Now;
                MessageToServer msg = new MessageToServer();
                msg.TransmitTime = DateTime.Now.ToString("o");
                msg.Type = MessageToServer.MessageType.ROOM_MANAGEMENT;
                msg.RoomRequest = new RoomManagementRequest();
                msg.RoomRequest.Type = RoomRequestType.STATS;
                _client.TransmitMessage(msg);
            }

            Text connectionStatus = GameObject.FindGameObjectWithTag("ConnectionStatus").GetComponent<Text>();
            if (_client.IsClosed())
            {
                connectionStatus.text = "Disconnected";
            }
            else if (_client.IsConnected())
            {
                connectionStatus.text = "";
            }
            else if (_client.IsConnecting())
            {
                connectionStatus.text = "Connecting...";
            }
            else if (_client.IsClosing())
            {
                connectionStatus.text = "Closing...";
            }

            _client.Update();
        }
    }
}
