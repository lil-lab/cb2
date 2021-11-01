using System;
using UnityEngine;

public class Prop
{
    private ActionQueue _actionQueue;
    private GameObject _asset;

    public Prop(GameObject prefab)
    {
        _actionQueue = new ActionQueue();
        _asset = GameObject.Instantiate(prefab, new Vector3(0, 0, 0), Quaternion.identity);
    }

    // Returns true if the actor is in the middle of an action.
    public bool IsBusy() { return _actionQueue.IsBusy(); }

    // Returns the actor's current location (or destination, if busy).
    public HecsCoord Location() { return _actionQueue.TargetState().Coord;  }

    // Returns the actor's current heading (or destination, if rotating).
    public float HeadingDegrees() { return _actionQueue.TargetState().HeadingDegrees;  }

    public void SetParent(GameObject parent)
    {
        _asset.transform.SetParent(parent.transform, false);
    }

    public void SetTag(string tag)
    {
        _asset.tag = tag;
    }

    public void Update()
    {
        _actionQueue.Update();

        State.Continuous state = _actionQueue.ContinuousState();
        // Update current location, orientation, and animation based on action queue.
        _asset.transform.position = Scale() * state.Position + new Vector3(0, Scale() * 0.1f, 0);
        _asset.transform.rotation = Quaternion.AngleAxis(state.HeadingDegrees, new Vector3(0, 1, 0));
        Animation animation = _asset.GetComponentInChildren<Animation>();
        if (state.Animation == ActionQueue.AnimationType.WALKING)
        {
            animation.Play("Armature|Walking");
        } else if (state.Animation == ActionQueue.AnimationType.IDLE) {
            // Fade into idle, to remove artifacts if we're in the middle of another animation.
            animation.CrossFade("Armature|Idle", 0.3f);
        } else
        { 
            // All other animations default to idle.
            animation.CrossFade("Armature|Idle", 0.3f);
	    }
    }

    // Flushes actions and deallocates the assets for this object.
    public void Destroy()
    {
        GameObject.Destroy(_asset);
    }

    // Flushes actions in flight.
    public void Flush()
    {
        _actionQueue.Flush();
    }

    public void AddAction(ActionQueue.IAction action)
    {
        _actionQueue.AddAction(action);
    }

    private float Scale()
    {
        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        HexGrid manager = obj.GetComponent<HexGrid>();
        return manager.Scale;
    }
}
