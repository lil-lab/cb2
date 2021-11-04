using System;
using UnityEngine;

public class Prop
{
    private ActionQueue _actionQueue;
    private GameObject _asset;

    public static Prop FromNetwork(Network.Prop netProp)
    {
        if (netProp.PropType != Network.PropType.SIMPLE)
        {
            Debug.Log("Warning, attempted to initialize simple prop from non-simple network message.");
            return null;
        }
        UnityAssetSource assetSource = new UnityAssetSource();
        GameObject obj = assetSource.Load((IAssetSource.AssetId)netProp.SimpleInit.AssetId);
        Prop prop = new Prop(obj);
        prop.AddAction(Init.InitAt(netProp.PropInfo.Location, netProp.PropInfo.RotationDegrees));
        return prop;
    }

    public Prop(GameObject obj)
    {
        _actionQueue = new ActionQueue();
        // If the GameObject we've been provided with is a prefab,
        // instantiate it in the game world.
        if (obj.scene.name == null)
        {
            _asset = GameObject.Instantiate(obj, new Vector3(0, 0, 0), Quaternion.identity);
        }
        else
        {
            _asset = obj;
        }
    }

    // Returns true if the actor is in the middle of an action.
    public bool IsBusy() { return _actionQueue.IsBusy(); }

    // Returns the actor's current location (or destination, if busy).
    public HecsCoord Location() { return _actionQueue.TargetState().Coord; }

    // Returns the actor's current heading (or destination, if rotating).
    public float HeadingDegrees() { return _actionQueue.TargetState().HeadingDegrees; }

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
        UnityAssetSource assetSource = new UnityAssetSource();
        _actionQueue.Update();

        State.Continuous state = _actionQueue.ContinuousState();
        // Update current location, orientation, and animation based on action queue.
        _asset.transform.position = Scale() * state.Position;
        _asset.transform.rotation = Quaternion.AngleAxis(state.HeadingDegrees, new Vector3(0, 1, 0));
        if (state.BorderRadius != 0)
        {
            if (_asset.transform.FindChild("Outline") == null)
            {
                GameObject outline = GameObject.Instantiate(assetSource.Load(IAssetSource.AssetId.CARD_BASE_1));
                outline.transform.localScale += new Vector3(state.BorderRadius, 0, state.BorderRadius);
                outline.tag = "Outline";
                Material mat = outline.GetComponent<Material>();
                if (mat != null)
                    mat.color = Color.blue;
                outline.transform.SetParent(_asset.transform);
            }
            Debug.Log("Outline exists: " + (_asset.transform.Find("Outline") != null));
        }
        else
        {
            Transform outline = _asset.transform.Find("Outline");
            if (outline != null)
            {
                outline.parent = null;
                GameObject.Destroy(outline.gameObject);
            }
        }
        Animation animation = _asset.GetComponentInChildren<Animation>();
        if (animation == null)
            return;
        if (state.Animation == ActionQueue.AnimationType.WALKING)
        {
            animation.Play("Armature|Walking");
        }
        else if (state.Animation == ActionQueue.AnimationType.IDLE)
        {
            // Fade into idle, to remove artifacts if we're in the middle of another animation.
            animation.CrossFade("Armature|Idle", 0.3f);
        }
        else
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
