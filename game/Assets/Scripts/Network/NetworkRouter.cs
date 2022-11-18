using System;
using System.Collections.Generic;
using UnityEngine;

namespace Network
{

    // Handles incoming and outgoing network messages. Multiplexes ActionQueue 
    // messages such that actions destined for the *active* player get routed to
    // the correct place. Handles state synchronization and forwards map updates
    // to the NetworkMapUpdate class. Also combines outgoing packets destined 
    // for the server.
    public class NetworkRouter
    {

        private Logger _logger;
        private readonly ClientConnection _client;
        private NetworkMapSource _mapSource;
        private readonly NetworkManager _networkManager;
        private EntityManager _entityManager;
        private MenuTransitionHandler _menuTransitionHandler;
        private Player _player;

        private List<MessageFromServer> _pendingMessages;

        public enum Mode
        {
            NONE = 0,
            NETWORK = 1,  // Used for actual games. NetworkManager receives messages.
            REPLAY = 2,  // Used to replay messages from the server. Doesn't relay to NetworkManager.
        }

        private Mode _mode = Mode.NONE;

        public NetworkRouter(ClientConnection client, NetworkMapSource mapSource, NetworkManager networkManager, EntityManager entityManager=null, Player player=null, Mode mode=Mode.NETWORK)
        {
            _client = client;
            _mapSource = mapSource;
            _networkManager = networkManager;
            _entityManager = entityManager;
            _player = player;
            _logger = Logger.GetTrackedLogger("NetworkRouter");
            _pendingMessages = new List<MessageFromServer>();
            if (_logger == null)
            {
                _logger = Logger.CreateTrackedLogger("NetworkRouter");
            }
            _mode = mode;

            if (_client != null) _client.RegisterHandler(this);
        }

        public bool PlayerIsSet()
        {
            return _player != null;
        }

        public void SetEntityManager(EntityManager entityManager)
        {
            _entityManager = entityManager;
        }

        public void ClearEntityManager()
        {
            _entityManager = null;
        }

        public void SetPlayer(Player player)
        {
            if (player == null) {
                Debug.Log("NetworkRouter player is null.");
            }
            _player = player;
        }

        public void SetMenuTransitionHandler(MenuTransitionHandler menuTransitionHandler)
        {
            _menuTransitionHandler = menuTransitionHandler;
        }

        public void ClearMenuTransitionHandler()
        {
            _menuTransitionHandler = null;
        }

        public void ClearPlayer()
        {
            _player = null;
        }

        public bool Initialized() {
            return _menuTransitionHandler != null && _player != null && _entityManager != null;
        }

        public void Update()
        {
            if (Initialized() && _pendingMessages.Count > 0)
            {
                foreach (MessageFromServer message in _pendingMessages)
                {
                    ProcessMessage(message);
                }
                _pendingMessages.Clear();
            }
        }

        public bool ApplyStateSyncToPlayer(StateSync stateSync)
        {
            if (_player == null) return false;
            _player.SetPlayerId(stateSync.player_id);
            _player.FlushActionQueue();
            foreach (Network.StateSync.Actor actor in stateSync.actors)
            {
                if (actor.actor_id == _player.PlayerId())
                {
                    _logger.Info("SETTING player asset id to " + actor.asset_id);
                    _player.SetAssetId(actor.asset_id);
                    ActionQueue.IAction action = TeleportToStartState(actor);
                    _player.AddAction(action);
                    continue;
                }
            }
            return true;
        }
        public bool ApplyStateSyncToEntityManager(StateSync stateSync)
        {
            if (_entityManager == null) return false;
            _entityManager.DestroyActors();
            foreach (Network.StateSync.Actor netActor in stateSync.actors)
            {
                if (netActor.actor_id == stateSync.player_id) continue;
                Actor actor = Actor.FromStateSync(netActor);
                actor.SetScale(1.8f);
                _entityManager.RegisterActor(netActor.actor_id, actor);
            }
            return true;
        }

        public bool ApplyPropUpdateToEntityManager(PropUpdate propUpdate)
        {
            _logger.Info("ApplyPropUpdateToEntityManager()");
            if (_entityManager == null) return false;
            _logger.Info("Applying prop update with " + propUpdate.props.Count + " props to entity manager...");
            _entityManager.QueueDestroyProps();
            foreach (Network.Prop netProp in propUpdate.props)
            {
                if (netProp.prop_type == PropType.CARD)
                {
                    _logger.Info("Registering card " + netProp.id);
                    CardBuilder cardBuilder = CardBuilder.FromNetwork(netProp);
                    _entityManager.RegisterProp(netProp.id, cardBuilder.Build());
                    if (netProp.card_init.selected)
                    {
                        _entityManager.AddAction(
                            netProp.id,
                            Outline.Select(netProp.prop_info.border_radius,
                                           netProp.prop_info.border_color,
                                           0.1f,
                                           netProp.prop_info.border_color_follower));
                    }
                    continue;
                }
                if (netProp.prop_type == PropType.SIMPLE)
                {
                    _logger.Info("Registering prop " + netProp.id);
                    global::Prop prop = global::Prop.FromNetwork(netProp);
                    _entityManager.RegisterProp(netProp.id, prop);
                    continue;
                }
                _logger.Warn("Unknown proptype encountered.");
            }
            return true;
        }

        private void ProcessMessage(MessageFromServer message)
        {
            if (message.type == MessageFromServer.MessageType.PING)
            {
                _logger.Info("Received ping.");
                if (_mode == Mode.NETWORK) _networkManager.RespondToPing();
                return;
            }
            if (message.type == MessageFromServer.MessageType.ACTIONS)
            {
                if (((_player == null) && (_mode == Mode.NETWORK)) || (_entityManager == null))
                {
                    _logger.Error("Player or entity manager not set, yet received state sync.");
                    return;
                }
                foreach (Network.Action networkAction in message.actions)
                {
                    ActionQueue.IAction action = ActionFromNetwork(networkAction);
                    if ((_mode == Mode.NETWORK) && (networkAction.id == _player.PlayerId()))
                    {
                        _player.ValidateHistory(action);
                        continue;
                    }
                    if (_player == null)
                    {
                        _logger.Error("Player not set, yet received action.");
                    }
                    if ((_mode == Mode.REPLAY) && (_player != null) && (networkAction.id == _player.PlayerId()))
                    {
                        _logger.Info("Forwarding action to player!");
                        _player.AddAction(action);
                        continue;
                    } else {
                        Debug.Log("Player ID: " + _player.PlayerId() + " networkAction.id: " + networkAction.id);
                    }
                    _entityManager.AddAction(networkAction.id, action);
                }
            }
            if (message.type == MessageFromServer.MessageType.STATE_SYNC)
            {
                if ((!ApplyStateSyncToPlayer(message.state)))
                {
                    _logger.Info("Player not set, yet received state sync.");
                }
                if (!ApplyStateSyncToEntityManager(message.state))
                {
                    _logger.Info("Entity manager not set, yet received state sync.");
                }
            }
            if (message.type == MessageFromServer.MessageType.STATE_MACHINE_TICK)
            {
                // Do nothing, this is more useful for bots.
            }
            if (message.type == MessageFromServer.MessageType.MAP_UPDATE)
            {
                if (_mapSource == null)
                {
                    _logger.Info("Network Router received map update but no map source to forward it to.");
                    return;
                }
                _mapSource.ReceiveMapUpdate(message.map_update);
            }
            if (message.type == MessageFromServer.MessageType.PROP_UPDATE)
            {
                if(!ApplyPropUpdateToEntityManager(message.prop_update))
                {
                    _logger.Info("Unable to apply prop update to entity manager... Saved for later.");
                }
            }
            if (message.type == MessageFromServer.MessageType.OBJECTIVE)
            {
                GameObject obj = GameObject.FindGameObjectWithTag(MenuTransitionHandler.TAG);
                if (obj == null)
                {
                    Debug.Log("Could not find menu transition handler object.");
                    return;
                }
                MenuTransitionHandler menuTransitionHandler = obj.GetComponent<MenuTransitionHandler>();
                if (menuTransitionHandler == null)
                {
                    Debug.Log("Could not find menu transition handler.");
                    return;
                }
                menuTransitionHandler.RenderObjectiveList(message.objectives);
            }
            if (message.type == MessageFromServer.MessageType.TURN_STATE)
            {
                DateTime transmitTime = DateTime.Parse(message.transmit_time, null, System.Globalization.DateTimeStyles.RoundtripKind);
                TurnState state = message.turn_state;
                if (_menuTransitionHandler == null)
                {
                    _logger.Warn("Menu transition handler not set, yet received turn state.");
                    return;
                }
                _menuTransitionHandler.HandleTurnState(transmitTime, state);
                _networkManager.HandleTurnState(state);
                if (_mode == Mode.NETWORK) _player.HandleTurnState(state);
            }
            if (message.type == MessageFromServer.MessageType.TUTORIAL_RESPONSE)
            {
                _networkManager.HandleTutorialResponse(message.tutorial_response);
            }
            if (message.type == MessageFromServer.MessageType.LIVE_FEEDBACK)
            {
                MenuTransitionHandler.TaggedInstance().HandleLiveFeedback(message.live_feedback);
            }
        }

        // For messages which don't require in-game UI to be rendered.
        public bool ProcessEarly(MessageFromServer message) {
            // Handle AUTH messages immediately.
            if (message.type == MessageFromServer.MessageType.GOOGLE_AUTH_CONFIRMATION)
            {
                // Static menu transition handler.
                _logger.Info("Received Google Auth Confirmation.");
                MenuTransitionHandler.HandleLoginStatus(message.google_auth_confirmation);
                if (message.google_auth_confirmation.success)
                {
                    _networkManager.OnAuthenticated();
                }
                return true;
            }
            return false;
        }

        public void HandleMessage(MessageFromServer message)
        {
            _logger.Info("Received message of type: " + message.type);
            if (message.type == MessageFromServer.MessageType.ROOM_MANAGEMENT)
            {
                if (_mode == Mode.NETWORK) _networkManager.HandleRoomManagement(message.room_management_response);
                return;
            }
            if (message.type == MessageFromServer.MessageType.TUTORIAL_RESPONSE)
            {
                if (_mode == Mode.NETWORK) _networkManager.HandleTutorialResponse(message.tutorial_response);
                return;
            }

            // Some messages can short-circuit here.
            if (ProcessEarly(message)) return;

            if (Initialized()) {
                ProcessMessage(message);
            } else {
                _pendingMessages.Add(message);
            }
        }

        public void TransmitAction(ActionQueue.IAction action)
        {
            if (_player == null)
            {
                _logger.Info("Can't send action to server; Player object null.");
                return;
            }
            if (_player.PlayerId() == -1)
            {
                _logger.Info("Can't send action to server; Player ID unknown.");
                return;
            }
            if (_client == null)
            {
                Debug.Log("Can't send action to server; Client object null.");
                return;
            }
            MessageToServer toServer = new MessageToServer();
            toServer.transmit_time = DateTime.UtcNow.ToString("o");
            toServer.type = MessageToServer.MessageType.ACTIONS;
            toServer.actions = new List<Action>();
            toServer.actions.Add(action.Packet(_player.PlayerId()));
            _client.TransmitMessage(toServer);
        }

        private ActionQueue.IAction TeleportToStartState(Network.StateSync.Actor actorState)
        {
            return new Init(new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.IDLE,
                Displacement = actorState.location,
                Rotation = actorState.rotation_degrees,
                DurationS = 0.001f,
                Expiration = DateTime.MaxValue,
            });
        }

        private ActionQueue.IAction ActionFromNetwork(Network.Action networkAction)
        {
            DateTime expiration = DateTime.Parse(networkAction.expiration, null,
                System.Globalization.DateTimeStyles.RoundtripKind);
            ActionQueue.ActionInfo info = new ActionQueue.ActionInfo()
            {
                Type = (ActionQueue.AnimationType)networkAction.animation_type,
                Displacement = networkAction.displacement,
                Rotation = networkAction.rotation,
                DurationS = networkAction.duration_s,
                BorderRadius = networkAction.border_radius,
                BorderColor = networkAction.border_color,
                Expiration = expiration,
                BorderColorFollowerPov = networkAction.border_color_follower_pov,
            };
            ActionQueue.IAction action;
            switch (networkAction.action_type)
            {
                case ActionType.INIT:
                    action = new Init(info);
                    break;
                case ActionType.INSTANT:
                    action = new Instant(info);
                    break;
                case ActionType.ROTATE:
                    action = new Rotate(info);
                    break;
                case ActionType.TRANSLATE:
                    action = new Translate(info);
                    break;
                case ActionType.OUTLINE:
                    action = new Outline(info);
                    break;
                default:
                    _logger.Info("Unknown action type encountered. Converting to instant.");
                    action = new Instant(info);
                    break;
            }
            return action;
        }
    }
}
