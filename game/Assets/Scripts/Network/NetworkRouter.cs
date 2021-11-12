using System;
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
        private ClientConnection _client;
        private NetworkMapSource _mapSource;
        private EntityManager _entityManager;
        private Player _player;
        private int _activeActorId = -1;

        public NetworkRouter(ClientConnection client, NetworkMapSource mapSource, EntityManager entityManager, Player player)
        {
            _client = client;
            _mapSource = mapSource;
            _entityManager = entityManager;
            _player = player;

            _client.RegisterHandler(this);
        }

        public void HandleMessage(MessageFromServer message)
        {
            Debug.Log("Received message of type: " + message.Type);
            if (message.Type == MessageFromServer.MessageType.ACTIONS)
            {
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
        }

        public void TransmitAction(ActionQueue.IAction action)
        {
            if (_activeActorId == -1)
            {
                Debug.Log("Can't send action to server; Player ID unknown.");
                return;
            }
            _client.TransmitAction(_activeActorId, action);
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
