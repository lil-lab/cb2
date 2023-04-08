using System;
using System.Collections;
using System.Collections.Generic;
using System.Collections.Specialized;
using System.Threading.Tasks;
using System.Web;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using UnityEngine.Networking;
using System.Linq;
using Newtonsoft.Json;

namespace Network
{
    public class NetworkManager : MonoBehaviour
    {
        public static string TAG = "NetworkManager";

        public static NetworkManager Instance;

        public readonly static string URL = "localhost:8080/";

        private readonly static double TICK_WAIT_TIMEOUT_S = 5.0;

        private ClientConnection _client;
        private NetworkMapSource _networkMapSource;
        private NetworkRouter _router;
        private EntityManager _entityManager;
        private Player _player;
        private MenuTransitionHandler _menuTransitionHandler;
        private DateTime _lastStatsPoll;
        private Network.Config _serverConfig;
        private Network.Config _replayConfig;
        private DateTime _lastServerConfigPoll = DateTime.MinValue;
        private bool _serverConfigPollInProgress = false;
        private Role _role = Network.Role.NONE;
        private Role _replayRole = Network.Role.NONE;
        private Role _currentTurn = Network.Role.NONE;
        private bool _waitingForTick = false;

        // The time at which we should stop waiting for a tick.
        // Tick waiting is a soft constraint - we don't want to wait forever and
        // freeze the client.
        private DateTime _tickWaitDeadline = DateTime.MinValue;

        // A JWT encoded Google OneTap token. See GoogleOneTapLogin.cs
        // https://www.rfc-editor.org/rfc/rfc7519
        // Don't try to decode this in the client. Instead pass it to the server and
        // have the server decode it, using Google's verifier library.
        private string _google_id_token = null;
        private bool _authenticated = false;

        private UserInfo _user_info = null;
        private bool _user_info_requested = false;

        private Logger _logger;

        public IMapSource MapSource()
        {
            Scene scene = SceneManager.GetActiveScene();
            if (scene.name == "menu_scene")
            {
                _logger.Info("Loading menu map");
                return new FixedMapSource();
            }
            if (_networkMapSource == null)
            {
                _logger.Warn("Retrieved map source before it was initialized.");
            }
            return _networkMapSource;
        }

        public NetworkMapSource NetworkMapSource()
        {
            return _networkMapSource;
        }

        public static NetworkManager TaggedInstance()
        {
            GameObject obj = GameObject.FindGameObjectWithTag(Network.NetworkManager.TAG);
            if (obj == null)
                return null;
            return obj.GetComponent<Network.NetworkManager>();
        }

        public static string BaseUrl(bool webSocket=true)
        {
            string url = URL;
            if (Application.absoluteURL == "")
            {
                if (webSocket)
                {
                    url = "ws://" + url;
                } else {
                    url = "http://" + url;
                }
            } else {
                // We can figure out the server's address based on Unity's API.
                Uri servedUrl = new Uri(Application.absoluteURL);

                string scheme = servedUrl.Scheme;
                if (webSocket) {
                    scheme = servedUrl.Scheme == "https" ? "wss" : "ws";
                }
                UriBuilder endpointUrlBuilder =
                    new UriBuilder(scheme, servedUrl.Host, servedUrl.Port);
                url = endpointUrlBuilder.Uri.AbsoluteUri;
            }
            return url;
        }

        public static Dictionary<string, string> UrlParameters()
        {
            // We can figure out the server's address based on Unity's API.
            if (Application.absoluteURL == "")
            {
                // Include the default parameter "lobby_name=open" so that the
                // unity client knows to use the open lobby.
                return new Dictionary<string, string>() {{"lobby_name", "open"}};
            }
            Uri servedUrl = new Uri(Application.absoluteURL);
            string query = servedUrl.Query;
            // Remove the initial ?.
            if (query.Length > 0 && query[0] == '?')
            {
                query = query.Substring(1);
            }
            NameValueCollection urlParameters = HttpUtility.ParseQueryString(query);
            // Convert the NameValueCollection to a Dictionary<string, string>.
            return urlParameters.AllKeys.ToDictionary(t => t, t => urlParameters[t]);
        }

        public Network.Config ServerConfig()
        {
            if (IsReplay()) {
                return _replayConfig;
            }
            if (_serverConfig == null)
            {
                _logger.Info("Retrieved server config before it was initialized.");
            }
            return _serverConfig;
        }

        public UserInfo GetUserInfo()
        {
            return _user_info;
        }

        public void SetUserInfo(UserInfo user_info)
        {
            _user_info = user_info;
        }

        public void SetGoogleOauthToken(string token)
        {
            _google_id_token = token;
            MenuTransitionHandler.LoginStarted();
        }

        public bool IsReplay()
        {
            return SceneManager.GetActiveScene().name == "replay_scene";
        }

        public void InjectReplayRole(Role role)
        {
            if (IsReplay())
            {
                _replayRole = role;
            } else {
                _logger.Warn("Attempted to inject replay role when not in replay scene.");
            }            
        }

        public void InjectReplayConfig(Network.Config config)
        {
            if (IsReplay())
            {
                _replayConfig = config;
                OnConfigReceived(_replayConfig);
            } else {
                _logger.Warn("Attempted to inject replay config when not in replay scene.");
            }
        }

        public void OnConfigReceived(Network.Config config)
        {
            // Applies any system settings the config might control.
            Application.targetFrameRate = config.fps_limit;

            if ((_serverConfig != null) && !NeedsGoogleAuth()) {
                // Hide the log out button.
                GameObject logOutButton = GameObject.FindGameObjectWithTag("GOOGLE_LOGOUT");
                if (logOutButton != null)
                {
                    logOutButton.SetActive(false);
                }
                // Hide the login status window.
                GameObject loginStatus = GameObject.FindGameObjectWithTag("LOGIN_STATUS_PANEL");
                if (loginStatus != null)
                {
                    loginStatus.SetActive(false);
                }
            }

            GoogleOneTapLogin login = GoogleOneTapLogin.TaggedInstance();
            if ((_serverConfig != null) && NeedsGoogleAuth() && (_google_id_token == null) && (!login.LoggedIn()) && (!login.LoginDisplayed()))
            {
                _logger.Info("Fetching google auth config");
                login.ShowLoginUI();
            }

            _logger.Info("Setting target FPS to " + config.fps_limit);
        }

        public Role Role()
        {
            if (IsReplay())
            {
                return _replayRole;
            }
            return _role;
        }

        public Role CurrentTurn()
        {
            return _currentTurn;
        }

        public void HandleTick()
        {
            _waitingForTick = false;
            _tickWaitDeadline = DateTime.MaxValue;
        }

        public bool TransmitAction(ActionQueue.IAction action)
        {
            if (_waitingForTick && DateTime.UtcNow > _tickWaitDeadline)
            {
                _logger.Warn("Timed out waiting for tick.");
                _waitingForTick = false;
                _tickWaitDeadline = DateTime.MaxValue;
            }
            if (_waitingForTick) {

                _logger.Warn("Attempted to transmit action while waiting for tick.");
                return false;
            }
            bool transmitted = _router.TransmitAction(action);
            if (transmitted)
            {
                _waitingForTick = true;
                _tickWaitDeadline = DateTime.UtcNow.AddSeconds(TICK_WAIT_TIMEOUT_S);
            }
            return transmitted;
        }

        public void RespondToPing()
        {
            MessageToServer toServer = new MessageToServer();
            toServer.transmit_time = DateTime.UtcNow.ToString("s");
            toServer.type = MessageToServer.MessageType.PONG;
            toServer.pong = new Pong{ping_receive_time = DateTime.UtcNow.ToString("o")};
            _client.TransmitMessage(toServer);
        }

        public void TransmitCancelPendingObjectives()
        {
            MessageToServer toServer = new MessageToServer();
            toServer.transmit_time = DateTime.UtcNow.ToString("s");
            toServer.type = MessageToServer.MessageType.CANCEL_PENDING_OBJECTIVES;
            _client.TransmitMessage(toServer);
        }

        public void TransmitObjective(ObjectiveMessage objective)
        {
            MessageToServer toServer = new MessageToServer();
            toServer.transmit_time = DateTime.UtcNow.ToString("s");
            toServer.type = MessageToServer.MessageType.OBJECTIVE;
            toServer.objective = objective;
            toServer.objective.sender = _role;
            _client.TransmitMessage(toServer);
        }

        public void TransmitLiveFeedback(LiveFeedback feedback)
        {
            MessageToServer toServer = new MessageToServer();
            toServer.transmit_time = DateTime.UtcNow.ToString("s");
            toServer.type = MessageToServer.MessageType.LIVE_FEEDBACK;
            toServer.live_feedback = feedback;
            _client.TransmitMessage(toServer);
        }

        public void TransmitObjectiveComplete(ObjectiveCompleteMessage objectiveComplete)
        {
            MessageToServer toServer = new MessageToServer();
            toServer.transmit_time = DateTime.UtcNow.ToString("s");
            toServer.type = MessageToServer.MessageType.OBJECTIVE_COMPLETE;
            toServer.objective_complete = objectiveComplete;
            _client.TransmitMessage(toServer);
        }

        public void TransmitTurnComplete()
        {
            MessageToServer toServer = new MessageToServer();
            toServer.transmit_time = DateTime.UtcNow.ToString("s");
            toServer.type = MessageToServer.MessageType.TURN_COMPLETE;
            _client.TransmitMessage(toServer);
        }

        public void TransmitReplayRequest(ReplayRequest request)
        {
            MessageToServer toServer = new MessageToServer();
            toServer.transmit_time = DateTime.UtcNow.ToString("s");
            toServer.type = MessageToServer.MessageType.REPLAY_REQUEST;
            toServer.replay_request = request;
            _client.TransmitMessage(toServer);
        }

        public void TransmitScenarioDownloadRequest()
        {
            MessageToServer toServer = new MessageToServer();
            toServer.transmit_time = DateTime.UtcNow.ToString("s");
            toServer.type = MessageToServer.MessageType.SCENARIO_DOWNLOAD;
            _client.TransmitMessage(toServer);
        }

        public void TransmitScenarioRequest(ScenarioRequest request)
        {
            MessageToServer toServer = new MessageToServer();
            toServer.transmit_time = DateTime.UtcNow.ToString("s");
            toServer.type = MessageToServer.MessageType.SCENARIO_REQUEST;
            toServer.scenario_request = request;
            _client.TransmitMessage(toServer);
        }

        public void Awake()
        {
            gameObject.tag = TAG;
            _logger = Logger.GetOrCreateTrackedLogger("NetworkManager");
        }

        // Called when a user clicks the "Join Game" menu button. Enters the game queue.
        public void JoinGame()
        {
            if ((_serverConfig != null) && NeedsGoogleAuth() && (!_authenticated))
            {
                _logger.Warn("Attempted to join game without authenticating.");
                return;
            }
            MessageToServer msg = new MessageToServer();
            msg.transmit_time = DateTime.UtcNow.ToString("s");
            msg.type = MessageToServer.MessageType.ROOM_MANAGEMENT;
            msg.room_request = new RoomManagementRequest();
            msg.room_request.type = RoomRequestType.JOIN;
            _logger.Info("Joining game...");
            _client.TransmitMessage(msg);
        }

        public void JoinAsLeader()
        {
            MessageToServer msg = new MessageToServer();
            msg.transmit_time = DateTime.UtcNow.ToString("s");
            msg.type = MessageToServer.MessageType.ROOM_MANAGEMENT;
            msg.room_request = new RoomManagementRequest();
            msg.room_request.type = RoomRequestType.JOIN_LEADER_ONLY;
            _logger.Info("Joining game as follower ...");
            _client.TransmitMessage(msg);
        }

        public void JoinAsFollower()
        {
            MessageToServer msg = new MessageToServer();
            msg.transmit_time = DateTime.UtcNow.ToString("s");
            msg.type = MessageToServer.MessageType.ROOM_MANAGEMENT;
            msg.room_request = new RoomManagementRequest();
            msg.room_request.type = RoomRequestType.JOIN_FOLLOWER_ONLY;
            _logger.Info("Joining game as follower ...");
            _client.TransmitMessage(msg);
        }

        public void StartLeaderTutorial()
        {
            StartTutorial(TutorialRequest.LEADER_TUTORIAL);
        }

        public void StartFollowerTutorial()
        {
            StartTutorial(TutorialRequest.FOLLOWER_TUTORIAL);
        }

        public void OnAuthenticated()
        {
            _authenticated = true;
        }

        public void StartTutorial(string tutorialName)
        {
            MessageToServer msg = new MessageToServer();
            msg.transmit_time = DateTime.UtcNow.ToString("s");
            msg.type = MessageToServer.MessageType.TUTORIAL_REQUEST;
            msg.tutorial_request = new TutorialRequest();
            msg.tutorial_request.type = TutorialRequestType.START_TUTORIAL;
            msg.tutorial_request.tutorial_name = tutorialName;
            _logger.Info("Joining tutorial...");
            _client.TransmitMessage(msg);
        }

        public void NextTutorialStep()
        {
            MessageToServer msg = new MessageToServer();
            msg.transmit_time = DateTime.UtcNow.ToString("s");
            msg.type = MessageToServer.MessageType.TUTORIAL_REQUEST;
            msg.tutorial_request = new TutorialRequest();
            msg.tutorial_request.type = Network.TutorialRequestType.REQUEST_NEXT_STEP;
            _logger.Info("Requesting next tutorial step...");
            _client.TransmitMessage(msg);            
        }

        // Pulls the player out of the wait queue to join a new game.
        public void CancelGameQueue()
        {
            MessageToServer msg = new MessageToServer();
            msg.transmit_time = DateTime.UtcNow.ToString("s");
            msg.type = MessageToServer.MessageType.ROOM_MANAGEMENT;
            msg.room_request = new RoomManagementRequest();
            msg.room_request.type = RoomRequestType.CANCEL;
            _client.TransmitMessage(msg);
        }

        // Leave an active game -- signals to the server that we are leaving.
        public void QuitGame()
        {
            MessageToServer msg = new MessageToServer();
            msg.transmit_time = DateTime.UtcNow.ToString("s");
            msg.type = MessageToServer.MessageType.ROOM_MANAGEMENT;
            msg.room_request = new RoomManagementRequest();
            msg.room_request.type = RoomRequestType.LEAVE;
            _client.TransmitMessage(msg);
            ReturnToMenu();
        }

        // Return to the main menu.
        public void ReturnToMenu()
        {
            if (_networkMapSource != null)
            {
                _networkMapSource.ClearMapUpdate();
            }
            _role = Network.Role.NONE;
            _currentTurn = Network.Role.NONE;
            if (_router != null)
            {
                _router.Clear();
            }
            SceneManager.LoadScene("menu_scene");
        }

        // Display the Game Over screen, with an optional explanation.
        public void DisplayGameOverMenu(string reason="")
        {
            MenuTransitionHandler menu = MenuTransitionHandler.TaggedInstance();
            if (menu != null)
            {
                menu.DisplayEndGameMenu(reason);
            }
        }

        public Util.Status InitializeEntityManager()
        {
            GameObject obj = GameObject.FindGameObjectWithTag(EntityManager.TAG);
            if (obj == null)
                return Util.Status.NotFound("Could not find tag: " + EntityManager.TAG);
            _entityManager = obj.GetComponent<EntityManager>();
            if (_entityManager == null)
                return Util.Status.NotFound("Could not find component: " + EntityManager.TAG);
            _router.SetEntityManager(_entityManager);
            return Util.Status.OkStatus();
        }

        public Util.Status InitializePlayer()
        {
            GameObject playerObj = GameObject.FindGameObjectWithTag(Player.TAG);
            if (playerObj == null)
                return Util.Status.NotFound("Could not find tag: " + Player.TAG);
            _player = playerObj.GetComponent<Player>();
            if (_player == null)
                return Util.Status.NotFound("Could not find component: " + Player.TAG);
            _router.SetPlayer(_player);
            return Util.Status.OkStatus();
        }

        public Util.Status InitializeMenuTransitionHandler()
        {
            GameObject obj = GameObject.FindGameObjectWithTag(MenuTransitionHandler.TAG);
            if (obj == null)
            {
                return Util.Status.NotFound("Could not find menu tag: " + MenuTransitionHandler.TAG);
            }
            _menuTransitionHandler = obj.GetComponent<MenuTransitionHandler>();
            if (_menuTransitionHandler == null)
                return Util.Status.NotFound("Could not find menu transition handler component.");
            _router.SetMenuTransitionHandler(_menuTransitionHandler);
            return Util.Status.OkStatus();
        }

        public Util.Status InitializeTaggedObjects()
        {
            Util.Status result = Util.Status.OkStatus();
            result.Chain(InitializeEntityManager());
            result.Chain(InitializePlayer());
            result.Chain(InitializeMenuTransitionHandler());
            return result;
        }

        public void RestartConnection() {
            _logger.Info("Restarting connection...");
            _client.Start();
            _authenticated = false;
        }

        // Start is called before the first frame update
        private void Start()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(this);  // Persist network connection between scene changes.
            } else if (Instance != this) {
                _logger.Warn("Tried to create duplicate network manager. Self-destructed game object.");
                DestroyImmediate(gameObject);
                return;
            }
            _networkMapSource = new NetworkMapSource();

            string url = "";
            if (Application.absoluteURL == "") {
                url = "ws://" + URL + "player_endpoint?lobby_name=open";
            } else {
                // We can figure out the server's address based on Unity's API.
                Uri servedUrl = new Uri(Application.absoluteURL);
                string websocketScheme = servedUrl.Scheme == "https" ? "wss" : "ws";
                UriBuilder endpointUrlBuilder =
                    new UriBuilder(websocketScheme, servedUrl.Host, servedUrl.Port,
                                   "/player_endpoint");
                if (servedUrl.Query.Length > 0)
                {
                    endpointUrlBuilder.Query = servedUrl.Query.Substring(1);  // Remove leading '?'
                }
                url = endpointUrlBuilder.Uri.AbsoluteUri;
            }
            _logger.Info("Using url: " + url);
            _client = new ClientConnection(url, /*autoReconnect=*/ true);
            _router = new NetworkRouter(_client, _networkMapSource, this, null, null);

            _client.Start();
            _authenticated = false;

            Util.Status result = InitializeTaggedObjects();
            if (!result.Ok())
            {
                _logger.Warn(result.ToString());
            }

            // Subscribe to new scene changes.
            SceneManager.sceneLoaded += OnSceneLoaded;

            _lastStatsPoll = DateTime.UtcNow;

            _lastServerConfigPoll = DateTime.UtcNow;
            _serverConfigPollInProgress = true;
            StartCoroutine(FetchConfig());
        }

        public void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            // Set log level.
            Logger.SetGlobalLogLevel(Logger.LogLevel.INFO);
            _logger.Info("Scene loaded: " + scene.name);
            if (scene.name == "menu_scene") {
                _router.SetMode(NetworkRouter.Mode.NETWORK);
                // Refetch config on menu scene. Then return.
                _lastServerConfigPoll = DateTime.UtcNow;
                _serverConfigPollInProgress = true;
                _user_info_requested = false;
                // When reloading the menu scene, we need to re-authenticate.
                _authenticated = false;
                StartCoroutine(FetchConfig());
                return;    
            }
            Util.Status result = InitializeTaggedObjects();
            if (!result.Ok())
            {
                _logger.Warn(result.ToString());
            }

            if (scene.name == "replay_scene")
            {
                _router.SetMode(NetworkRouter.Mode.REPLAY);
            } else {
                _router.SetMode(NetworkRouter.Mode.NETWORK);
            }
        }

        public void OnApplicationQuit()
        {
            _client.OnApplicationQuit();
        }

        public void HandleTutorialResponse(TutorialResponse tutorialResponse)
        {
            if (tutorialResponse.type == TutorialResponseType.STARTED)
            {
                _logger.Info("Tutorial started.");
                _router.Clear();
                SceneManager.LoadScene("tutorial_scene");
                _role = tutorialResponse.Role();
            }
            else if (tutorialResponse.type == TutorialResponseType.COMPLETED)
            {
                _logger.Info("Tutorial completed.");
                DisplayGameOverMenu("Tutorial completed. Your participation has been recorded.");
            }
            else if (tutorialResponse.type == TutorialResponseType.STEP)
            {
                _logger.Info("Tutorial next step received.");
                TutorialManager.TaggedInstance().HandleTutorialStep(tutorialResponse.step);
            }
        }

        public void HandleRoomManagement(RoomManagementResponse response)
        {
            if (response.type == RoomResponseType.JOIN_RESPONSE)
            {
                if (response.join_response.joined)
                {
                    _logger.Info("Joined room as " + response.join_response.role + "!");
                    _router.Clear();
                    SceneManager.LoadScene("game_scene");
                    _role = response.join_response.role;
                } else if (response.join_response.booted_from_queue) {
                    _logger.Info("Booted from queue.");
                    GameObject bootedUi = GameObject.FindGameObjectWithTag("QUEUE_TIMEOUT_UI");
                    Canvas bootedCanvas = bootedUi.GetComponent<Canvas>();
                    bootedCanvas.enabled = true;
                } else {
                    _logger.Info("Waiting for room. Position in queue: " + response.join_response.place_in_queue);
                }
            }
            else if (response.type == RoomResponseType.LEAVE_NOTICE)
            {
                _logger.Info("Game ended. Reason: " + response.leave_notice.reason);
                Scene scene = SceneManager.GetActiveScene();
                if (scene.name != "menu_scene")
                {
                    DisplayGameOverMenu("Game ended. Reason: " + response.leave_notice.reason);
                }
            }
            else if (response.type == RoomResponseType.STATS)
            {
                _logger.Debug("Stats: " + response.stats.ToString());
                GameObject obj = GameObject.FindGameObjectWithTag("Stats");
                if (obj == null) return;
                Text stats = obj.GetComponent<Text>();
                stats.text = "Players in game: " + response.stats.players_in_game + "\n" +
                             "Games: " + response.stats.number_of_games + "\n" +
                             "Players Waiting: " + response.stats.players_waiting + "\n";
            }
            else if (response.type == RoomResponseType.ERROR)
            {
                _logger.Info("Received room management error: " + response.error);
            }
            else if (response.type == RoomResponseType.MAP_SAMPLE)
            {
                _networkMapSource.ReceiveMapUpdate(response.map_update);
                MessageFromServer map_update_message = new MessageFromServer();
                map_update_message.type = MessageFromServer.MessageType.MAP_UPDATE;
                map_update_message.map_update = response.map_update;
                map_update_message.transmit_time = DateTime.UtcNow.ToString();
                _router.HandleMessage(map_update_message);
            }
            else
            {
                _logger.Info("Received unknown room management response type: " + response.type);
            }
        }

        public void HandleTurnState(TurnState state)
        {
            _currentTurn = state.turn;
        }

        public void RequestMapSample()
        {
            MessageToServer msg = new MessageToServer();
            msg.transmit_time = DateTime.UtcNow.ToString("s");
            msg.type = MessageToServer.MessageType.ROOM_MANAGEMENT;
            msg.room_request = new RoomManagementRequest();
            msg.room_request.type = RoomRequestType.MAP_SAMPLE;
            _client.TransmitMessage(msg);
        }

        // Update is called once per frame
        void Update()
        {
            if (_router != null)
            {
                _router.Update();
            }
            // If it's been more than 5 mins since the last poll and _serverConfig is null, poll the server for the config.
            // Alternatively, if _serverConfig is out of date and it's been > 1 seconds since the last poll, also poll the server.
            if (((_serverConfig != null) && (DateTime.UtcNow.Subtract(_serverConfig.timestamp).TotalMinutes > 5)) || 
                ((_serverConfig == null) && (DateTime.UtcNow.Subtract(_lastServerConfigPoll).TotalSeconds > 1) && !_serverConfigPollInProgress))
            {
                _logger.Info("Starting fetch config coroutine. poll in progress: " + _serverConfigPollInProgress);
                _lastServerConfigPoll = DateTime.UtcNow;
                _serverConfigPollInProgress = true;
                StartCoroutine(FetchConfig());
            }
            GameObject statsObj = GameObject.FindGameObjectWithTag("Stats");
            if (((DateTime.UtcNow - _lastStatsPoll).Seconds > 3) && (statsObj != null) && (statsObj.activeInHierarchy))
            {
                _logger.Debug("Requesting stats..");
                _lastStatsPoll = DateTime.UtcNow;
                MessageToServer msg = new MessageToServer();
                msg.transmit_time = DateTime.UtcNow.ToString("s");
                msg.type = MessageToServer.MessageType.ROOM_MANAGEMENT;
                msg.room_request = new RoomManagementRequest();
                msg.room_request.type = RoomRequestType.STATS;
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
                _serverConfig = null;
                connectionStatus.text = "Connecting...";
            }
            else if (_client.IsClosing())
            {
                connectionStatus.text = "Closing...";
            }

            // If we're connected to the server, we need google authentication, and we have a token, then we need to send it to the server.
            if ((_serverConfig != null) && NeedsGoogleAuth() && (_google_id_token != null) && (!_authenticated))
            {
                _logger.Info("Sending google auth token to server.");
                MessageToServer msg = new MessageToServer();
                msg.transmit_time = DateTime.UtcNow.ToString("s");
                msg.type = MessageToServer.MessageType.GOOGLE_AUTH;
                msg.google_auth = new GoogleAuth();
                msg.google_auth.token = _google_id_token;
                _client.TransmitMessage(msg);
                _google_id_token = null;
            }

            if (_client.IsConnected() && (_serverConfig != null) && (!NeedsGoogleAuth() || _authenticated) && (_user_info == null) && (!_user_info_requested))
            {
                _logger.Info("Requesting user info.");
                MessageToServer msg = new MessageToServer();
                msg.transmit_time = DateTime.UtcNow.ToString("s");
                msg.type = MessageToServer.MessageType.USER_INFO;
                _client.TransmitMessage(msg);
                _user_info_requested = true;
            }

            _client.Update();
        }
        private IEnumerator FetchConfig()
        {
            string base_url = Network.NetworkManager.BaseUrl(/*websocket=*/false);
            string request_url = base_url + "data/config";
            _logger.Info("Fetching config from " + request_url);
            using (UnityWebRequest webRequest = UnityWebRequest.Get(request_url))
            {
                // Request and wait for the desired page.
                yield return webRequest.SendWebRequest();

                switch (webRequest.result)
                {
                    case UnityWebRequest.Result.ConnectionError:
                    case UnityWebRequest.Result.DataProcessingError:
                        _logger.Warn("Error: " + webRequest.error);
                        break;
                    case UnityWebRequest.Result.ProtocolError:
                        _logger.Warn("HTTP Error: " + webRequest.error);
                        break;
                    case UnityWebRequest.Result.Success:
                        _logger.Info("Received: " + webRequest.downloadHandler.text);
                        _serverConfig = JsonConvert.DeserializeObject<Network.Config>(webRequest.downloadHandler.text);
                        _serverConfig.timestamp = DateTime.UtcNow;
                        OnConfigReceived(_serverConfig);
                        break;
                }
            }

            _logger.Info("Done with fetch config coroutine");
            _serverConfigPollInProgress = false;
        }

        public LobbyInfo ServerLobbyInfo()
        {
            Config c = ServerConfig();
            if (c == null)
            {
                return null;
            }
            Dictionary<string, string> urlParameters = UrlParameters();
            if (!urlParameters.ContainsKey("lobby_name"))
            {
                return null;
            }
            string lobby_name = urlParameters["lobby_name"];
            for (int i = 0; i < c.lobbies.Count; i++)
            {
                if (c.lobbies[i].name == lobby_name)
                {
                    return c.lobbies[i];
                }
            }
            return null;
        }

        private bool NeedsGoogleAuth()
        {
            // Start the connection to the server. If the lobby is a Google lobby, wait until receiving an Oauth token.
            Dictionary<string, string> urlParameters = UrlParameters();
            LobbyType type = _serverConfig.LobbyTypeFromName("default");
            if (urlParameters.ContainsKey("lobby_name")) {
                type = _serverConfig.LobbyTypeFromName(urlParameters["lobby_name"]);
            }

            return (type == LobbyType.GOOGLE) || (type == LobbyType.GOOGLE_LEADER);
        }
    }
}
