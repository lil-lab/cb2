using System;
using System.Collections.Generic;
using UnityEngine;

// Manages Props & Actors.
public class EntityManager : MonoBehaviour
{
    public static string TAG = "EntityManager";

    public void Awake()
    {
        gameObject.tag = TAG;
    }

    private Dictionary<int, Actor> _actors;
    private Dictionary<int, Prop> _props;

    public EntityManager()
    {
        _actors = new Dictionary<int, Actor>();
        _props = new Dictionary<int, Prop>();
    }

    public int NumberOfActors()
    {
        return _actors.Count;
    }

    public int NumberOfProps()
    {
        return _props.Count;
    }

    public void AddAction(int id, ActionQueue.IAction action)
    {
        if (_actors.ContainsKey(id))
        {
            _actors[id].AddAction(action);
            return;
        }
        if (_props.ContainsKey(id))
        {
            _props[id].AddAction(action);
            return;
        }
        Debug.Log("Warning, invalid actor id received: " + _actors.Count);
    }

    public void RegisterProp(int id, Prop prop)
    {
        if (_props.ContainsKey(id))
        {
            Debug.Log("Ignoring duplicate prop registration: " + id);
            return;
        }
        _props[id] = prop;
    }

    public void RegisterActor(int id, Actor actor)
    {
        if (_actors.ContainsKey(id))
        {
            Debug.Log("Ignoring duplicate actor registration: " + id);
            return;
        }
        _actors[id] = actor;
    }

    public void FlushActors()
    {
        foreach (var kvPair in _actors)
        {
            int actorId = kvPair.Key;
            _actors[actorId].Flush();
        }
    }

    public void FlushProps()
    {
        foreach (var kvPair in _props)
        {
            int propId = kvPair.Key;
            _props[propId].Flush();
        }
    }

    public void DestroyActors()
    {
        FlushActors();
        foreach (var kvPair in _actors)
        {
            int actorId = kvPair.Key;
            _actors[actorId].Destroy();
        }

        _actors = new Dictionary<int, Actor>();
    }

    public void DestroyProps()
    {
        FlushProps();
        foreach (var kvPair in _props)
        {
            int propId = kvPair.Key;
            _props[propId].Destroy();
        }

        _props = new Dictionary<int, Prop>();
    }

    public void Update()
    {
        foreach (var kvPair in _actors)
        {
            int actorId = kvPair.Key;
            _actors[actorId].Update();
        }
        foreach (var kvPair in _props)
        {
            int propId = kvPair.Key;
            _props[propId].Update();
        }
    }
}
