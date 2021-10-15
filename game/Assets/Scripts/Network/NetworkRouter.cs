using System;
using UnityEngine;

namespace Network
{
	public class NetworkRouter
	{
		private NetworkMapSource _mapSource;
		private ActorManager _actorManager;
		public NetworkRouter(NetworkMapSource mapSource, ActorManager actorManager)
		{
			_mapSource = mapSource;
			_actorManager = actorManager;
		}

		public void HandleMessage(MessageFromServer message)
		{
			if (message.Type == MessageFromServer.MessageType.ACTIONS)
			{
				foreach (Network.Action networkAction in message.Actions)
				{
					_actorManager.AddAction(networkAction.ActorId, FromNetworkAction(networkAction));
				}
			}
		}

		private ActionQueue.IAction FromNetworkAction(Network.Action networkAction)
		{
			ActionQueue.ActionInfo info = new ActionQueue.ActionInfo()
			{
				Type = (ActionQueue.AnimationType)networkAction.AnimationType,
				Start = networkAction.Start,
				Destination = networkAction.Destination,
				StartHeading = networkAction.StartHeading,
				DestinationHeading = networkAction.DestinationHeading,
				DurationS = networkAction.DurationS,
				Expiration = networkAction.Expiration,
			};
			ActionQueue.IAction action;
			switch (networkAction.ActionType)
			{
				case ActionType.INSTANT:
					action = new Instant(info);
					break;
				case ActionType.ROTATE:
					action = new Rotate(info);
					break;
				case ActionType.TRANSLATE:
					action = new Translate(info);
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
