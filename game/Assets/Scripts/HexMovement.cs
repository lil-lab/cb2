using System;
using System.Collections.Generic;
using UnityEngine;

public class HexMovement
{
    public enum AnimationType
    { 
        IDLE,
        WALKING,
        INSTANT,
        TRANSLATE,
        ACCEL_DECEL,
        SKIPPING,
        ROTATE,
    }

    public class MovementInfo
    {
        public AnimationType Type;
        public HecsCoord Start;  // Where the move starts from.
        public HecsCoord Destination;  // Where the object should end up.
        public float StartHeading;
        public float DestinationHeading;
        public float DurationS;  // Seconds.
        public DateTime Expiration;  // Ditch the movement at this point.
    };

    // A kind of movement (walk, skip, jump). This is distinctly different from 
    // the model animation (though related).  The movement defines how an object
    // moves through space as a function of time. The animation defines how the
    // object mesh changes (leg movement motion, etc) as the object moves.
    public interface IMovement
    {
        void Start();
        MovementInfo Info();
        void Update();
        Vector3 Location();
        float Heading();
        bool IsDone();
    }

    private Queue<IMovement> _movementQueue;
    private HecsCoord _location;  // Current loc or destination of current movement.
    private float _heading;  // Current heading (or desination of current movement).
    private bool _movementInProgress;

    public HexMovement()
    {
        _movementQueue = new Queue<IMovement>();
        _movementInProgress = false;
    }

    // Adds a move to the queue.
    public void AddMovement(IMovement movement)
    {
        if (movement == null)
	    {
            return;
	    }
        _movementQueue.Enqueue(movement);
    }

    // Is the object in the middle of a movement.
    public bool IsBusy()
    {
        return _movementQueue.Count != 0;
    }

    public float ImmediateHeading()
    { 
        if (IsBusy())
	    {
            return _movementQueue.Peek().Heading();
	    }
        return _heading;
    } 

    // The current location at this moment, including coordinates along the path
    // if the object is moving.
    public Vector3 ImmediateLocation()
    {
        // If we're moving, return the current movement location.
        if (IsBusy())
        {
            return _movementQueue.Peek().Location();
        }
        (float x, float z) = _location.Cartesian();
        // TODO(sharf): For supporting mountains, this will need to peek at the
        // GridManager to get the local Y-coordinate.
        return new Vector3(x, 0, z);
    }

    // Return the current animation type.
    public AnimationType ImmediateAnimation() { 
        if (IsBusy()) {
            return _movementQueue.Peek().Info().Type;
	    }
        return AnimationType.IDLE;
    }

    public HecsCoord TargetLocation()
    {
        return _location;
    }

    public float TargetHeading()
    {
        return _heading;
    }

    public void Update()
    { 
        // If there's no animation in progress, begin the next animation in the queue.
        if (_movementQueue.Count > 0 && !_movementInProgress) {
            _movementQueue.Peek().Start();
            _movementInProgress = true;
	    }

        // Flush any finished animations.
        while (_movementQueue.Count > 0 && _movementQueue.Peek().IsDone())
	    {
            // Even if we're fast-forwarding through an expired animation, the
	        // resulting location/heading should be kept.
            _location = _movementQueue.Peek().Info().Destination;
            _heading = _movementQueue.Peek().Info().DestinationHeading;
            _movementQueue.Dequeue();
            _movementInProgress = false;
	    }

        if (_movementQueue.Count == 0) return;

        if (_movementInProgress)
		    _movementQueue.Peek().Update();
    }
}
