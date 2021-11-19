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
        private int _activeActorId = -1;

        public NetworkRouter(ClientConnection client, NetworkMapSource mapSource, NetworkManager networkManager, EntityManager entityManager, Player player)
        {
            _client = client;
            _mapSource = mapSource;
            _networkManager = networkManager;
            _entityManager = entityManager;
            _player = player;

            _client.RegisterHandler(this);
        }

        public void SetEntityManager(EntityManager entityManager)
        {
            _entityManager = entityManager;
        }

        public void SetPlayer(Player player)
        {
            _player = player;
        }

        public void HandleMessage(MessageFromServer message)
        {
            Debug.Log("Received message of type: " + message.Type);
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
                    if (networkAction.Id == _activeActorId)
                    {
                        _player.ValidateHistory(action);
                        continue;
                    }
                    _entityManager.AddAction(networkAction.Id, action);
                }
            }
            if (message.Type == MessageFromServer.MessageType.STATE_SYNC)
            {
                if (_player == null || _entityManager == null)
                {
                    Debug.LogError("Player or entity manager not set, yet received state sync.");
                    return;
                }
                _activeActorId = message.State.PlayerId;
                _entityManager.DestroyActors();
                _player.FlushActionQueue();
                foreach (Network.StateSync.Actor actor in message.State.Actors)
                {
                    if (actor.ActorId == _activeActorId)
                    {
                        ActionQueue.IAction action = TeleportToStartState(actor);
                        _player.AddAction(action);
                        continue;
                    }
                    _entityManager.RegisterActor(actor.ActorId, Actor.FromStateSync(actor));
                }
            }
            if (message.Type == MessageFromServer.MessageType.MAP_UPDATE)
            {
                if (_entityManager == null)
                {
                    Debug.LogError("Entity manager not set, yet received state sync.");
                    return;
                }
                if (_mapSource == null)
                {
                    Debug.Log("Network Router received map update but no map source to forward it to.");
                    return;
                }
                _mapSource.ReceiveMapUpdate(message.MapUpdate);
                _entityManager.DestroyProps();
                foreach (Network.Prop netProp in message.MapUpdate.Props)
                {
                    if (netProp.PropType == PropType.CARD)
                    {
                        CardBuilder cardBuilder = CardBuilder.FromNetwork(netProp);
                        _entityManager.RegisterProp(netProp.Id, cardBuilder.Build());
                        if (netProp.CardInit.Selected)
                        {
                            _entityManager.AddAction(netProp.Id, Outline.Select(netProp.PropInfo.BorderRadius, 0.1f));
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
            }
            if (message.Type == MessageFromServer.MessageType.ROOM_MANAGEMENT)
            {
                _networkManager.HandleRoomManagement(message.RoomManagementResponse);
            }
        }

        public void TransmitAction(ActionQueue.IAction action)
        {
            if (_activeActorId == -1)
            {
                Debug.Log("Can't send action to server; Player ID unknown.");
                return;
            }

            MessageToServer toServer = new MessageToServer();
            toServer.TransmitTime = DateTime.Now.ToString("o");
            toServer.Type = MessageToServer.MessageType.ACTIONS;
            toServer.Actions = new List<Action>();
            toServer.Actions.Add(action.Packet(_activeActorId));
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
