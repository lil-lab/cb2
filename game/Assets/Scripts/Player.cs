using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Player : MonoBehaviour
{
    public float TurnSpeed = 2;  // Turns/Second.
    public float MoveSpeed = 0.2f;  // Cells/Second.
    public int StartingRow = 10;
    public int StartingCol = 13;
    public bool ShowHeading = false;

    private HexMovement _actionQueue;

    private float Scale()
    {
        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        HexGrid manager = obj.GetComponent<HexGrid>();
        return manager.Scale;
    }

    void Start()
    {
        _actionQueue = new HexMovement();

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

    // If public member ShowHeading is true, these 3 debug boxes appear on the grid.
    private GameObject _facing;
    private GameObject _upperRight;
    private GameObject _right;

    private void DrawHeading()
    {
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
        if (_actionQueue.ImmediateAnimation() == HexMovement.AnimationType.WALKING)
        {
            animation.Play("Armature|Walking");
        } else if (_actionQueue.ImmediateAnimation() == HexMovement.AnimationType.IDLE) {
            // Fade into idle, to remove artifacts if we're in the middle of another animation.
            animation.CrossFade("Armature|Idle", 0.3f);
        }

        // If we're in an animation, don't check for user input.
        if (_actionQueue.IsBusy()) return;

        if (Input.GetKey(KeyCode.UpArrow)) {
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
