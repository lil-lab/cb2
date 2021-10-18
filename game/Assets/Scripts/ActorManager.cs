using System;
using System.Collections.Generic;
using UnityEngine;

// TODO(sharf): This can be factored into the same class as "Actors".
public class ActorManager : MonoBehaviour
{
    public static string TAG = "ActorManager";

    public void Awake()
    {
        gameObject.tag = TAG;
    }

    private Dictionary<int, Actor> _actors;

    public ActorManager()
    {
        _actors = new Dictionary<int, Actor>();
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

    public void RegisterActor(int actorId, Actor actor)
    {
        if (_actors.ContainsKey(actorId))
        {
            Debug.Log("Ignoring duplicate actor registration: " + actorId);
            return;
        }
        _actors[actorId] = actor;
    }

    public void Flush()
    { 
        foreach (var kvPair in _actors)
        {
            int actorId = kvPair.Key;
            _actors[actorId].Flush();
	    }

        _actors = new Dictionary<int, Actor>(); 
    }

    public void Update()
    {
	    foreach (var kvPair in _actors)
        {
            int actorId = kvPair.Key;
            _actors[actorId].Update();
	    } 
    }
}
