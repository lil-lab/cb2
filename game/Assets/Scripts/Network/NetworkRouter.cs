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

            _client.RegisterHandler(this);
        }

        public void SetEntityManager(EntityManager entityManager)
        {
            _entityManager = entityManager;
            if (_pendingStateSync != null)
            {
                Debug.Log("EntityManager receiving pending state sync.");
                ApplyStateSyncToEntityManager(_pendingStateSync);
            }
            if (_pendingMapUpdate != null)
            {
                Debug.Log("EntityManager receiving pending map update.");
                ApplyMapUpdateToEntityManager(_pendingMapUpdate);
            }
        }

        public void SetPlayer(Player player)
        {
            _player = player;
            if (_pendingStateSync != null)
            {
                Debug.Log("Player receiving pending state sync.");
                ApplyStateSyncToPlayer(_pendingStateSync);
            }
        }

        public bool ApplyStateSyncToPlayer(StateSync stateSync)
        {
            if (_player == null) return false;
            _player.SetPlayerId(stateSync.PlayerId);
            _player.FlushActionQueue();
            foreach (Network.StateSync.Actor actor in stateSync.Actors)
            {
                if (actor.ActorId == _player.PlayerId())
                {
                    Debug.Log("SETTING player asset id to " + actor.AssetId);
                    _player.SetAssetId(actor.AssetId);
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
            foreach (Network.StateSync.Actor actor in stateSync.Actors)
            {
                if (actor.ActorId == stateSync.PlayerId) continue;
                _entityManager.RegisterActor(actor.ActorId, Actor.FromStateSync(actor));
            }
            return true;
        }

        public bool ApplyMapUpdateToEntityManager(MapUpdate mapUpdate)
        {
            if (_entityManager == null) return false;
            _entityManager.QueueDestroyProps();
            foreach (Network.Prop netProp in mapUpdate.Props)
            {
                if (netProp.PropType == PropType.CARD)
                {
                    CardBuilder cardBuilder = CardBuilder.FromNetwork(netProp);
                    _entityManager.RegisterProp(netProp.Id, cardBuilder.Build());
                    if (netProp.CardInit.Selected)
                    {
                        _entityManager.AddAction(
                            netProp.Id,
                            Outline.Select(netProp.PropInfo.BorderRadius,
                                           netProp.PropInfo.BorderColor,
                                           0.1f));
                    }
                    continue;
                }
                if (netProp.PropType == PropType.SIMPLE)
                {
                    global::Prop prop = global::Prop.FromNetwork(netProp);
                    _entityManager.RegisterProp(netProp.Id, prop);
                    continue;
                }
                Debug.LogWarning("Unknown proptype encountered.");
            }
            return true;
        }
        public void HandleMessage(MessageFromServer message)
        {
            Debug.Log("Received message of type: " + message.Type);
            if (message.Type == MessageFromServer.MessageType.PING)
            {
                Debug.Log("Received ping.");
                _networkManager.RespondToPing();
                return;
            }
            if (message.Type == MessageFromServer.MessageType.ACTIONS)
            {
                if (_player == null || _entityManager == null)
                {
                    Debug.LogError("Player or entity manager not set, yet received state sync.");
                    return;
                }
                foreach (Network.Action networkAction in message.Actions)
                {
                    ActionQueue.IAction action = ActionFromNetwork(networkAction);
                    if (networkAction.Id == _player.PlayerId())
                    {
                        _player.ValidateHistory(action);
                        continue;
                    }
                    _entityManager.AddAction(networkAction.Id, action);
                }
            }
            if (message.Type == MessageFromServer.MessageType.STATE_SYNC)
            {
                if (!ApplyStateSyncToPlayer(message.State))
                {
                    Debug.Log("Player not set, yet received state sync.");
                    _pendingStateSync = message.State;
                }
                if (!ApplyStateSyncToEntityManager(message.State))
                {
                    Debug.Log("Entity manager not set, yet received state sync.");
                    _pendingStateSync = message.State;
                }
            }
            if (message.Type == MessageFromServer.MessageType.MAP_UPDATE)
            {
                if (_mapSource == null)
                {
                    Debug.Log("Network Router received map update but no map source to forward it to.");
                    return;
                }
                _mapSource.ReceiveMapUpdate(message.MapUpdate);
                if(!ApplyMapUpdateToEntityManager(message.MapUpdate))
                {
                    Debug.Log("Unable to apply map update to entity manager... Saved for later.");
                    _pendingMapUpdate = message.MapUpdate;
                }
            }
            if (message.Type == MessageFromServer.MessageType.ROOM_MANAGEMENT)
            {
                _networkManager.HandleRoomManagement(message.RoomManagementResponse);
            }
            if (message.Type == MessageFromServer.MessageType.OBJECTIVE)
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
                menuTransitionHandler.RenderObjectiveList(message.Objectives);
            }
            if (message.Type == MessageFromServer.MessageType.TURN_STATE)
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
                TurnState state = message.TurnState;
                DateTime transmitTime = DateTime.Parse(message.TransmitTime, null, System.Globalization.DateTimeStyles.RoundtripKind);
                menuTransitionHandler.HandleTurnState(transmitTime, state);
                _networkManager.HandleTurnState(state);
                _player.HandleTurnState(state);
            }
            if (message.Type == MessageFromServer.MessageType.TUTORIAL_RESPONSE)
            {
                _networkManager.HandleTutorialResponse(message.TutorialResponse);
            }
            if (message.Type == MessageFromServer.MessageType.LIVE_FEEDBACK)
            {
                Debug.Log("Received Live Feedback: " + message.LiveFeedback);
                MenuTransitionHandler.TaggedInstance().HandleLiveFeedback(message.LiveFeedback);
            }
        }

        public void TransmitAction(ActionQueue.IAction action)
        {
            if (_player == null)
            {
                Debug.Log("Can't send action to server; Player object null.");
                return;
            }
            if (_player.PlayerId() == -1)
            {
                Debug.Log("Can't send action to server; Player ID unknown.");
                return;
            }
            MessageToServer toServer = new MessageToServer();
            toServer.TransmitTime = DateTime.Now.ToString("o");
            toServer.Type = MessageToServer.MessageType.ACTIONS;
            toServer.Actions = new List<Action>();
            toServer.Actions.Add(action.Packet(_player.PlayerId()));
            _client.TransmitMessage(toServer);
        }

        private ActionQueue.IAction TeleportToStartState(Network.StateSync.Actor actorState)
        {
            return new Init(new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.IDLE,
                Displacement = actorState.Location,
                Rotation = actorState.RotationDegrees,
                DurationS = 0.001f,
                Expiration = DateTime.MaxValue,
            });
        }

        private ActionQueue.IAction ActionFromNetwork(Network.Action networkAction)
        {
            DateTime expiration = DateTime.Parse(networkAction.Expiration, null,
                System.Globalization.DateTimeStyles.RoundtripKind);
            ActionQueue.ActionInfo info = new ActionQueue.ActionInfo()
            {
                Type = (ActionQueue.AnimationType)networkAction.AnimationType,
                Displacement = networkAction.Displacement,
                Rotation = networkAction.Rotation,
                DurationS = networkAction.DurationS,
                BorderRadius = networkAction.BorderRadius,
                BorderColor = networkAction.BorderColor,
                Expiration = expiration,
            };
            ActionQueue.IAction action;
            switch (networkAction.ActionType)
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
                    Debug.Log("Unknown action type encountered. Converting to instant.");
                    action = new Instant(info);
                    break;
            }
            return action;
        }
    }
}
