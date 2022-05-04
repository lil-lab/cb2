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
        private Player _player;

        private StateSync _pendingStateSync;
        private MapUpdate _pendingMapUpdate;

        public NetworkRouter(ClientConnection client, NetworkMapSource mapSource, NetworkManager networkManager, EntityManager entityManager, Player player)
        {
            _client = client;
            _mapSource = mapSource;
            _networkManager = networkManager;
            _entityManager = entityManager;
            _player = player;
            _pendingStateSync = null;
            _logger = Logger.GetTrackedLogger("NetworkRouter");
            if (_logger == null)
            {
                _logger = Logger.CreateTrackedLogger("NetworkRouter");
            }
            _client.RegisterHandler(this);
        }

        public void SetEntityManager(EntityManager entityManager)
        {
            _entityManager = entityManager;
            if (_pendingStateSync != null)
            {
                _logger.Info("EntityManager receiving pending state sync.");
                ApplyStateSyncToEntityManager(_pendingStateSync);
            }
            if (_pendingMapUpdate != null)
            {
                _logger.Info("EntityManager receiving pending map update.");
                ApplyMapUpdateToEntityManager(_pendingMapUpdate);
            }
        }

        public void SetPlayer(Player player)
        {
            _player = player;
            if (_pendingStateSync != null)
            {
                _logger.Info("Player receiving pending state sync.");
                ApplyStateSyncToPlayer(_pendingStateSync);
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

        public bool ApplyMapUpdateToEntityManager(MapUpdate mapUpdate)
        {
            _logger.Info("ApplyMapUpdateToEntityManager()");
            if (_entityManager == null) return false;
            _logger.Info("Applying map update to entity manager...");
            _entityManager.QueueDestroyProps();
            foreach (Network.Prop netProp in mapUpdate.props)
            {
                if (netProp.prop_type == PropType.CARD)
                {
                    CardBuilder cardBuilder = CardBuilder.FromNetwork(netProp);
                    _entityManager.RegisterProp(netProp.id, cardBuilder.Build());
                    if (netProp.card_init.selected)
                    {
                        _entityManager.AddAction(
                            netProp.id,
                            Outline.Select(netProp.prop_info.border_radius,
                                           netProp.prop_info.border_color,
                                           0.1f));
                    }
                    continue;
                }
                if (netProp.prop_type == PropType.SIMPLE)
                {
                    global::Prop prop = global::Prop.FromNetwork(netProp);
                    _entityManager.RegisterProp(netProp.id, prop);
                    continue;
                }
                _logger.Warn("Unknown proptype encountered.");
            }
            return true;
        }
        public void HandleMessage(MessageFromServer message)
        {
            _logger.Info("Received message of type: " + message.type);
            if (message.type == MessageFromServer.MessageType.PING)
            {
                _logger.Info("Received ping.");
                _networkManager.RespondToPing();
                return;
            }
            if (message.type == MessageFromServer.MessageType.ACTIONS)
            {
                if (_player == null || _entityManager == null)
                {
                    _logger.Error("Player or entity manager not set, yet received state sync.");
                    return;
                }
                foreach (Network.Action networkAction in message.actions)
                {
                    ActionQueue.IAction action = ActionFromNetwork(networkAction);
                    if (networkAction.id == _player.PlayerId())
                    {
                        _player.ValidateHistory(action);
                        continue;
                    }
                    _entityManager.AddAction(networkAction.id, action);
                }
            }
            if (message.type == MessageFromServer.MessageType.STATE_SYNC)
            {
                if (!ApplyStateSyncToPlayer(message.state))
                {
                    _logger.Info("Player not set, yet received state sync.");
                    _pendingStateSync = message.state;
                }
                if (!ApplyStateSyncToEntityManager(message.state))
                {
                    _logger.Info("Entity manager not set, yet received state sync.");
                    _pendingStateSync = message.state;
                }
            }
            if (message.type == MessageFromServer.MessageType.MAP_UPDATE)
            {
                if (_mapSource == null)
                {
                    _logger.Info("Network Router received map update but no map source to forward it to.");
                    return;
                }
                _mapSource.ReceiveMapUpdate(message.map_update);
                if(!ApplyMapUpdateToEntityManager(message.map_update))
                {
                    _logger.Info("Unable to apply map update to entity manager... Saved for later.");
                    _pendingMapUpdate = message.map_update;
                }
            }
            if (message.type == MessageFromServer.MessageType.ROOM_MANAGEMENT)
            {
                _networkManager.HandleRoomManagement(message.room_management_response);
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
                TurnState state = message.turn_state;
                DateTime transmitTime = DateTime.Parse(message.transmit_time, null, System.Globalization.DateTimeStyles.RoundtripKind);
                menuTransitionHandler.HandleTurnState(transmitTime, state);
                _networkManager.HandleTurnState(state);
                _player.HandleTurnState(state);
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
            MessageToServer toServer = new MessageToServer();
            toServer.transmit_time = DateTime.Now.ToString("o");
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
