using System;
using UnityEngine;

public class Actor
{
    private ActionQueue _actionQueue;
    private GameObject _asset;

    // If _debuggingEnabled is true, these 3 boxes indicate the actor's heading.
    private bool _debuggingEnabled;
    private GameObject _facing;
    private GameObject _upperRight;
    private GameObject _right;

    public static Actor FromStateSync(Network.StateSync.Actor netActor)
    {
        UnityAssetSource assetLoader = new UnityAssetSource();
        GameObject asset = assetLoader.Load((IAssetSource.AssetId)netActor.AssetId);
        Actor actor = new Actor(asset);
        // Instantly move the actor to its starting location.
        actor.AddAction(new Instant(new ActionQueue.ActionInfo()
        {
            Type = ActionQueue.AnimationType.IDLE,
            Start = netActor.Location,
            Destination = netActor.Location,
            StartHeading = netActor.RotationDegrees,
            DestinationHeading = netActor.RotationDegrees,
            DurationS = 0.001f,
            Expiration = DateTime.MaxValue,
        }));
        return actor;
    }

    public Actor(GameObject prefab)
    {
        _actionQueue = new ActionQueue();
        _asset = GameObject.Instantiate(prefab, new Vector3(0, 0, 0), Quaternion.identity);
        _debuggingEnabled = false;
    }

    // Returns true if the actor is in the middle of an action.
    public bool IsBusy() { return _actionQueue.IsBusy(); }

    // Returns the actor's current location (or destination, if busy).
    public HecsCoord Location() { return _actionQueue.TargetLocation();  }

    // Returns the actor's current heading (or destination, if rotating).
    public float HeadingDegrees() { return _actionQueue.TargetHeading();  }

    public void SetParent(GameObject parent)
    {
        _asset.transform.SetParent(parent.transform);
    }

    public void EnableDebugging()
    {
        if (_debuggingEnabled) return;
        _debuggingEnabled = true;
        _facing = GameObject.CreatePrimitive(PrimitiveType.Cube);
        _upperRight = GameObject.CreatePrimitive(PrimitiveType.Cube);
        _right = GameObject.CreatePrimitive(PrimitiveType.Cube);
    }

    public void DisableDebugging()
    {
        if (!_debuggingEnabled) return;
        _debuggingEnabled = false;
        GameObject.Destroy(_facing);
        GameObject.Destroy(_upperRight);
        GameObject.Destroy(_right);
        _facing = null;
        _upperRight = null;
        _right = null;
    }

    public void SetTag(string tag)
    {
        _asset.tag = tag;
    }

    public void Update()
    {
        if (_debuggingEnabled) { DrawHeading(); }

        _actionQueue.Update();

        // Update current location, orientation, and animation based on action queue.
        _asset.transform.position = Scale() * _actionQueue.ImmediateLocation() + new Vector3(0, Scale() * 0.1f, 0);
        _asset.transform.rotation = Quaternion.AngleAxis(-60 + _actionQueue.ImmediateHeading(), new Vector3(0, 1, 0));
        Animation animation = _asset.GetComponent<Animation>();
        if (_actionQueue.ImmediateAnimation() == ActionQueue.AnimationType.WALKING)
        {
            animation.Play("Armature|Walking");
        } else if (_actionQueue.ImmediateAnimation() == ActionQueue.AnimationType.IDLE) {
            // Fade into idle, to remove artifacts if we're in the middle of another animation.
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

    private void DrawHeading()
    {
        // Draw UR and heading debug lines.
        (float urx, float urz) = _actionQueue.TargetLocation().UpRight().Cartesian();
        _upperRight.transform.position = new Vector3(urx, 0.1f, urz) * Scale();
        (float rx, float rz) = _actionQueue.TargetLocation().Right().Cartesian();
        _right.transform.position = new Vector3(rx, 0.1f, rz) * Scale();
        _right.GetComponent<Renderer>().material.color = Color.blue;

        (float hx, float hz) = _actionQueue.TargetLocation().NeighborAtHeading(_actionQueue.TargetHeading()).Cartesian();
        _facing.transform.position = new Vector3(hx, 0.1f, hz) * Scale();
    }
}
