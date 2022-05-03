using System;
using UnityEngine;

public class Actor
{
    private Prop _prop;

    // If _debuggingEnabled is true, these 3 boxes indicate the actor's heading.
    private bool _debuggingEnabled;
    private GameObject _facing;
    private GameObject _upperRight;
    private GameObject _right;

    public static Actor FromStateSync(Network.StateSync.Actor netActor)
    {
        UnityAssetSource assetLoader = new UnityAssetSource();
        GameObject asset = assetLoader.Load((IAssetSource.AssetId)netActor.asset_id);
        Actor actor = new Actor(asset, (IAssetSource.AssetId)netActor.asset_id);
        // Instantly move the actor to its starting location.
        actor.AddAction(new Init(new ActionQueue.ActionInfo()
        {
            Type = ActionQueue.AnimationType.IDLE,
            Displacement = netActor.location,
            Rotation = netActor.rotation_degrees,
            DurationS = 0.001f,
            Expiration = DateTime.MaxValue,
        }));
        return actor;
    }

    public Actor(GameObject prefab, IAssetSource.AssetId assetId)
    {
        _prop = new Prop(prefab, assetId);
        _prop.SetScale(1.8f);
        _debuggingEnabled = false;
    }

    public GameObject Find(string path){
        return _prop.Find(path);
    }

    // Returns true if the actor is in the middle of an action.
    public bool IsBusy() { return _prop.IsBusy(); }

    // Returns the actor's current location (or destination, if busy).
    public HecsCoord Location() { return _prop.Location();  }

    // Returns the actor's worldspace cooordinates.
    public Vector3 Position() { return _prop.Position(); }

    // Returns the actor's current heading (or destination, if rotating).
    public float HeadingDegrees() { return _prop.HeadingDegrees();  }

    public void SetParent(GameObject parent)
    {
        _prop.SetParent(parent);
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
        _prop.SetTag(tag);
    }

    public void Update()
    {
        if (_debuggingEnabled) { DrawHeading(); }

        _prop.Update();
    }

    // Flushes actions and deallocates the assets for this object.
    public void Destroy()
    {
        _prop.Destroy();
    }

    // Flushes actions in flight.
    public void Flush()
    {
        _prop.Flush();
    }

    public void AddAction(ActionQueue.IAction action)
    {
        _prop.AddAction(action);
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
        (float urx, float urz) = _prop.Location().UpRight().Cartesian();
        _upperRight.transform.position = new Vector3(urx, 0.1f, urz) * Scale();
        (float rx, float rz) = _prop.Location().Right().Cartesian();
        _right.transform.position = new Vector3(rx, 0.1f, rz) * Scale();
        _right.GetComponent<Renderer>().material.color = Color.blue;

        (float hx, float hz) = _prop.Location().NeighborAtHeading(_prop.HeadingDegrees()).Cartesian();
        _facing.transform.position = new Vector3(hx, 0.1f, hz) * Scale();
    }
}
