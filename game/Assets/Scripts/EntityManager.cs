using System;
using System.Linq;
using System.Collections.Generic;
using UnityEngine;

// Manages Props & Actors.
public class EntityManager : MonoBehaviour
{
    public static string TAG = "EntityManager";

    private Logger _logger;

    public void Awake()
    {
        gameObject.tag = TAG;
        _logger = Logger.GetOrCreateTrackedLogger(TAG);
    }

    public static EntityManager TaggedInstance()
    {
        GameObject obj = GameObject.FindGameObjectWithTag(EntityManager.TAG);
        if (obj == null)
            return null;
        return obj.GetComponent<EntityManager>();
    }

    private Dictionary<int, Actor> _actors;
    private Dictionary<int, Prop> _props;
    private List<Prop> _graveyard;

    public EntityManager()
    {
        _actors = new Dictionary<int, Actor>();
        _props = new Dictionary<int, Prop>();
        _graveyard = new List<Prop>();
    }

    public int NumberOfActors()
    {
        return _actors.Count;
    }

    public int NumberOfProps()
    {
        return _props.Count;
    }

    public List<Prop> Props()
    {
        return _props.Values.ToList();
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
        _logger.Warn("Warning, invalid actor id received: " + id);
    }

    public void RegisterProp(int id, Prop prop)
    {
        _logger.Info("Registering prop: " + id);
        if (_props.ContainsKey(id))
        {
            _logger.Info("Ignoring duplicate prop registration: " + id);
            return;
        }
        _props[id] = prop;
    }

    public void RegisterActor(int id, Actor actor)
    {
        _logger.Info("Registering actor: " + id);
        if (_actors.ContainsKey(id))
        {
            _logger.Info("Ignoring duplicate actor registration: " + id);
            return;
        }
        _actors[id] = actor;
    }

    public void DestroyProp(int id)
    {
        if (_props.ContainsKey(id))
        {
            _props[id].Destroy();
            _props.Remove(id);
            return;
        }
        _logger.Warn("Warning, invalid prop id received: " + id);
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
        _logger.Info("Destroying actors");
        FlushActors();
        foreach (var kvPair in _actors)
        {
            int actorId = kvPair.Key;
            if (!_actors.ContainsKey(actorId))
                continue;
            _actors[actorId].Destroy();
        }

        _actors = new Dictionary<int, Actor>();
    }

    public void DestroyProps()
    {
        _logger.Info("Destroying props");
        FlushProps();
        foreach (var kvPair in _props)
        {
            int propId = kvPair.Key;
            if (!_props.ContainsKey(propId))
                continue;
            _props[propId].Destroy();
        }

        _props = new Dictionary<int, Prop>();
    }

    // Queue all current props to eventually self-destruct. Move them to a separate graveyard collection until then.
    public void QueueDestroyProps()
    {
        _logger.Info("Queuing props for destruction");
        foreach (var kvPair in _props)
        {
            int propId = kvPair.Key;
            if (!_props.ContainsKey(propId))
                continue;
            Prop prop = _props[propId];
            prop.AddAction(Death.DieImmediately());
            _graveyard.Add(prop);
        }
        _props = new Dictionary<int, Prop>();
        _logger.Info("Queued " + _graveyard.Count + " props for destruction.");
    }

    public void QueueDestroyProp(int id)
    {
        if (!_props.ContainsKey(id))
            return;
        Prop prop = _props[id];
        prop.AddAction(Death.DieImmediately());
        _graveyard.Add(prop);
        _props.Remove(id);
        return;
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
        // Remove destroyed props.
        _props = _props.Where(x => !x.Value.IsDestroyed()).ToDictionary(x => x.Key, x => x.Value);
        foreach (var prop in _graveyard)
        {
            prop.Update();
        }
        // Remove destroyed props from graveyard.
        _graveyard.RemoveAll(x => x.IsDestroyed());
    }
}
