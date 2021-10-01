using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Player : MonoBehaviour
{
    public float TurnSpeed = 2;  // Turns/Second.
    public float MoveSpeed = 0.2f;  // Cells/Second.
    public int StartingRow = 10;
    public int StartingCol = 13;

    private HexMovement _actionQueue;
    private Animator _animator;

    private float Scale()
    {
        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        HexGrid manager = obj.GetComponent<HexGrid>();
        return manager.Scale;
    }

    void Start()
    {
        _actionQueue = new HexMovement();
        _animator = GetComponent<Animator>();

        // Set the starting location by enqueuing a teleport to the target location.
        var startingLocation = new HexMovement.MovementInfo
        {
            Type = HexMovement.AnimationType.INSTANT,
            Destination = HecsCoord.FromOffsetCoordinates(13, 10),
            DestinationHeading = 0
        };
        _actionQueue.AddMovement(new Instant(startingLocation));

        _facing = GameObject.CreatePrimitive(PrimitiveType.Cube);
        _upperRight = GameObject.CreatePrimitive(PrimitiveType.Cube);
        _right = GameObject.CreatePrimitive(PrimitiveType.Cube);
    }

    private GameObject _facing;
    private GameObject _upperRight;
    private GameObject _right;

    void Update()
    {
        _actionQueue.Update();

        // Draw UR and heading debug lines.
        (float urx, float urz) = _actionQueue.TargetLocation().UpRight().Cartesian();
        _upperRight.transform.position = new Vector3(urx, 0.1f, urz) * Scale();
        (float rx, float rz) = _actionQueue.TargetLocation().Right().Cartesian();
        _right.transform.position = new Vector3(rx, 0.1f, rz) * Scale();
        _right.GetComponent<Renderer>().material.color = Color.blue;

        (float hx, float hz) = _actionQueue.TargetLocation().NeighborAtHeading(_actionQueue.ImmediateHeading()).Cartesian();
        _facing.transform.position = new Vector3(hx, 0.1f, hz) * Scale();

        // Update current location & orientation based on action queue.
        gameObject.transform.position = Scale() * _actionQueue.ImmediateLocation();
        gameObject.transform.rotation = Quaternion.AngleAxis(-60 + _actionQueue.ImmediateHeading(), new Vector3(0, 1, 0));

        // If we're in an animation, don't check for user input.
        if (_actionQueue.IsBusy()) return;

        if (Input.GetKey(KeyCode.UpArrow)) {
            Debug.Log("Up");
            var animationInfo = new HexMovement.MovementInfo()
            {
                Type = HexMovement.AnimationType.WALKING,
                Destination = _actionQueue.TargetLocation().NeighborAtHeading(_actionQueue.TargetHeading()),
                DestinationHeading = _actionQueue.TargetHeading(),
                Start = _actionQueue.TargetLocation(),
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / MoveSpeed,
            };
            _actionQueue.AddMovement(new Translate(animationInfo));
            return;
	    }
        if (Input.GetKey(KeyCode.DownArrow))
        { 
            Debug.Log("Down");
            var animationInfo = new HexMovement.MovementInfo()
            {
                Type = HexMovement.AnimationType.WALKING,
                Destination = _actionQueue.TargetLocation().NeighborAtHeading(_actionQueue.TargetHeading() + 180.0f),
                DestinationHeading = _actionQueue.TargetHeading(),
                Start = _actionQueue.TargetLocation(),
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / MoveSpeed,
            };
            _actionQueue.AddMovement(new Translate(animationInfo));
            return;
	    }
        if (Input.GetKey(KeyCode.LeftArrow))
        {
            Debug.Log("Left");
            if (_actionQueue.IsBusy()) {
                Debug.Log("Queue busy");
	        }
            var animationInfo = new HexMovement.MovementInfo()
            {
                Type = HexMovement.AnimationType.ROTATE,
                Destination = _actionQueue.TargetLocation(),
                DestinationHeading = _actionQueue.TargetHeading() - 60.0f,
                Start = _actionQueue.TargetLocation(),
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / TurnSpeed,
            };
            _actionQueue.AddMovement(new Rotate(animationInfo));
            if (_actionQueue.IsBusy()) {
                Debug.Log("Queue busy");
	        }
            return;
	    }
        if (Input.GetKey(KeyCode.RightArrow))
        {
            Debug.Log("Right");
            var animationInfo = new HexMovement.MovementInfo()
            {
                Type = HexMovement.AnimationType.ROTATE,
                Destination = _actionQueue.TargetLocation(),
                DestinationHeading = _actionQueue.TargetHeading() + 60.0f,
                Start = _actionQueue.TargetLocation(),
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / TurnSpeed,
            };
            _actionQueue.AddMovement(new Rotate(animationInfo));
            return;
	    }
    }
}
