using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Player : MonoBehaviour
{
    public float TurnSpeed = 2;  // Turns/Second.
    public float MoveSpeed = 2;  // Cells/Second.

    private HexMovement _actionQueue;

    void Start()
    {
        _actionQueue = new HexMovement();        
    }

    void Update()
    {
        _actionQueue.Update();

        // Update current location & orientation based on action queue.
        gameObject.transform.position = _actionQueue.ImmediateLocation();
        gameObject.transform.rotation = Quaternion.AngleAxis(_actionQueue.ImmediateHeading(), new Vector3(0, 1, 0));

        // If we're in an animation, don't check for user input.
        if (_actionQueue.IsBusy()) return;

        if (Input.GetKey(KeyCode.UpArrow)) {
            var animationInfo = new HexMovement.AnimationInfo()
            {
                Type = HexMovement.AnimationType.WALKING,
                Destination = _actionQueue.TargetLocation().NeighborAtHeading(_actionQueue.TargetHeading()),
                DestinationHeading = _actionQueue.TargetHeading(),
                Start = _actionQueue.TargetLocation(),
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / MoveSpeed,
            };
            _actionQueue.AddAnimation(new Translate(animationInfo));
            return;
	    }
        if (Input.GetKey(KeyCode.DownArrow))
        { 
            var animationInfo = new HexMovement.AnimationInfo()
            {
                Type = HexMovement.AnimationType.WALKING,
                Destination = _actionQueue.TargetLocation().NeighborAtHeading(_actionQueue.TargetHeading() + 180.0f),
                DestinationHeading = _actionQueue.TargetHeading(),
                Start = _actionQueue.TargetLocation(),
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / MoveSpeed,
            };
            _actionQueue.AddAnimation(new Translate(animationInfo));
            return;
	    }
        if (Input.GetKey(KeyCode.LeftArrow))
        {
            var animationInfo = new HexMovement.AnimationInfo()
            {
                Type = HexMovement.AnimationType.ROTATE,
                Destination = _actionQueue.TargetLocation(),
                DestinationHeading = _actionQueue.TargetHeading() - 60.0f,
                Start = _actionQueue.TargetLocation(),
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / TurnSpeed,
            };
            _actionQueue.AddAnimation(new Translate(animationInfo));
            return;
	    }
        if (Input.GetKey(KeyCode.RightArrow))
        {
            var animationInfo = new HexMovement.AnimationInfo()
            {
                Type = HexMovement.AnimationType.ROTATE,
                Destination = _actionQueue.TargetLocation(),
                DestinationHeading = _actionQueue.TargetHeading() + 60.0f,
                Start = _actionQueue.TargetLocation(),
                StartHeading = _actionQueue.TargetHeading(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / TurnSpeed,
            };
            _actionQueue.AddAnimation(new Translate(animationInfo));
            return;
	    }
    }
}
