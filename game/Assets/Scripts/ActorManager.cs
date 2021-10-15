using System;
using System.Collections.Generic;
using UnityEngine;

public class ActorManager
{
    private Dictionary<int, IActor> _actors;
    private int _activeActor = -1;

    public ActorManager()
    {
        _actors = new Dictionary<int, IActor>();
    }

    public int NumberOfActors()
    {
        return _actors.Count;
    }

    public void AddAction(int actorId, ActionQueue.IAction action)
    {
        if (!_actors.ContainsKey(actorId))
        {
            Debug.Log("Warning, invalid actor id received: " + _actors.Count);
            return; 
	    }
        _actors[actorId].AddAction(action);
    }

    public void RegisterActor(int actorId, IActor actor)
    {
        if (_actors.ContainsKey(actorId))
        {
            Debug.Log("Ignoring duplicate actor registration: " + actorId);
            return;
        }
        _actors[actorId] = actor;
    }

    public void SetActiveActor(int actorId)
    {
        if (!_actors.ContainsKey(_activeActor))
        {
            Debug.Log("Warning, retrieved invalid active action queue ID!");
            return;
	    }
        _activeActor = actorId;
    }

    public ActionQueue ActiveQueue()
    { 
        if (!_actors.ContainsKey(_activeActor))
        {
            Debug.Log("Warning, retrieved active queue before it was known!");
            return null;
	    }
        return _activeActor;
    }

    public void ClearRegistry()
    {
        _actors = new Dictionary<int, IActor>(); 
    }
}
