using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Player : MonoBehaviour
{
    public float TurnSpeed = 2;  // Turns/Second.
    public float MoveSpeed = 0.2f;  // Cells/Second.

    public bool ForceStartingPosition = false;
    public int StartingRow = 9;
    public int StartingCol = 7;
    public bool ShowHeading = false;

    private Network.NetworkManager _network;

    private ActionQueue _actionQueue;

    public void Awake()
    {
        GameObject obj = GameObject.FindGameObjectWithTag(Network.NetworkManager.TAG);
        _network = obj.GetComponent<Network.NetworkManager>();
    }

    private float Scale()
    {
        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        HexGrid manager = obj.GetComponent<HexGrid>();
        return manager.Scale;
    }

    void Start()
    {
        _facing = GameObject.CreatePrimitive(PrimitiveType.Cube);
        _upperRight = GameObject.CreatePrimitive(PrimitiveType.Cube);
        _right = GameObject.CreatePrimitive(PrimitiveType.Cube);
    }

    // If public member ShowHeading is true, these 3 debug boxes appear on the grid.
    private GameObject _facing;
    private GameObject _upperRight;
    private GameObject _right;

    private void DrawHeading()
    {
        if (_actionQueue == null)
        {
            return;
	    }
        // Draw UR and heading debug lines.
        (float urx, float urz) = _actionQueue.TargetLocation().UpRight().Cartesian();
        _upperRight.transform.position = new Vector3(urx, 0.1f, urz) * Scale();
        (float rx, float rz) = _actionQueue.TargetLocation().Right().Cartesian();
        _right.transform.position = new Vector3(rx, 0.1f, rz) * Scale();
        _right.GetComponent<Renderer>().material.color = Color.blue;

        (float hx, float hz) = _actionQueue.TargetLocation().NeighborAtHeading(_actionQueue.ImmediateHeading()).Cartesian();
        _facing.transform.position = new Vector3(hx, 0.1f, hz) * Scale();
    }

    void Update()
    {
        if (_actionQueue == null)
        {
            var actionQueue = ActiveActionQueue();
            if (actionQueue == null)
            {
                return;
            }

             _actionQueue = actionQueue;

             if (ForceStartingPosition)
             {
                 // Set the starting location by enqueuing a teleport to the target location.
                 var startingLocation = new ActionQueue.ActionInfo
                 {
                     Type = ActionQueue.AnimationType.INSTANT,
                     Destination = HecsCoord.FromOffsetCoordinates(StartingRow, StartingCol),
                     DestinationHeading = 0
                 };
                 _actionQueue.AddAction(new Instant(startingLocation));
             }
	    }
        _actionQueue.Update();

        // Debug mode optionally draw some cubes displaying heading.
        if (ShowHeading)
        {
            _facing.SetActive(true);
            _upperRight.SetActive(true);
            _right.SetActive(true);
            DrawHeading();
	    } else
	    {
            _facing.SetActive(false);
            _upperRight.SetActive(false);
            _right.SetActive(false);
	    }

        // Update current location, orientation, and animation based on action queue.
        gameObject.transform.position = Scale() * _actionQueue.ImmediateLocation() + new Vector3(0, Scale() * 0.1f, 0);
        gameObject.transform.rotation = Quaternion.AngleAxis(-60 + _actionQueue.ImmediateHeading(), new Vector3(0, 1, 0));
        Animation animation = GetComponent<Animation>();
        if (_actionQueue.ImmediateAnimation() == ActionQueue.AnimationType.WALKING)
        {
            animation.Play("Armature|Walking");
        } else if (_actionQueue.ImmediateAnimation() == ActionQueue.AnimationType.IDLE) {
            // Fade into idle, to remove artifacts if we're in the middle of another animation.
            animation.CrossFade("Armature|Idle", 0.3f);
        }

        // If we're in an animation, don't check for user input.
        if (_actionQueue.IsBusy()) return;

        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        HexGrid grid = obj.GetComponent<HexGrid>();

        HecsCoord currentLocation = _actionQueue.TargetLocation();
        HecsCoord forwardLocation = _actionQueue.TargetLocation().NeighborAtHeading(_actionQueue.TargetHeading());
        HecsCoord backLocation = _actionQueue.TargetLocation().NeighborAtHeading(_actionQueue.TargetHeading() + 180);

        if (Input.GetKey(KeyCode.UpArrow) &&
	        !grid.EdgeBetween(currentLocation, forwardLocation))
        { 
            var animationInfo = new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.WALKING,
                Destination = forwardLocation,
                DestinationHeading = _actionQueue.TargetHeading(),
                Start = currentLocation,
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / MoveSpeed,
            };
            _actionQueue.AddAction(new Translate(animationInfo));
            return;
	    }
        if (Input.GetKey(KeyCode.DownArrow) &&
	        !grid.EdgeBetween(currentLocation, backLocation))
        { 
            var animationInfo = new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.WALKING,
                Destination = backLocation,
                DestinationHeading = _actionQueue.TargetHeading(),
                Start = currentLocation,
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / MoveSpeed,
            };
            _actionQueue.AddAction(new Translate(animationInfo));
            return;
	    }
        if (Input.GetKey(KeyCode.LeftArrow))
        {
            var animationInfo = new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.ROTATE,
                Destination = _actionQueue.TargetLocation(),
                DestinationHeading = _actionQueue.TargetHeading() - 60.0f,
                Start = _actionQueue.TargetLocation(),
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / TurnSpeed,
            };
            _actionQueue.AddAction(new Rotate(animationInfo));
            return;
	    }
        if (Input.GetKey(KeyCode.RightArrow))
        {
            var animationInfo = new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.ROTATE,
                Destination = _actionQueue.TargetLocation(),
                DestinationHeading = _actionQueue.TargetHeading() + 60.0f,
                Start = _actionQueue.TargetLocation(),
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / TurnSpeed,
            };
            _actionQueue.AddAction(new Rotate(animationInfo));
            return;
	    }
    }

    private ActionQueue ActiveActionQueue()
    {
        GameObject obj = GameObject.FindGameObjectWithTag(Actors.TAG);
        ActorManager manager = obj.GetComponent<Actors>().Manager();
        return manager.ActiveQueue();
    }
}
