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

    public class AnimationInfo
    {
        public AnimationType Type;
        public HecsCoord Start;  // Where the animation starts from.
        public HecsCoord Destination;  // Where the object should end up.
        public float StartHeading;
        public float DestinationHeading;
        public float DurationS;  // Seconds.
        public DateTime Expiration;  // Ditch the animation at this point.
    };

    public interface IAnimation
    {
        void Start();
        AnimationInfo Info();
        void Update();
        Vector3 Location();
        float Heading();
        bool IsDone();
    }

    private Queue<IAnimation> _animationQueue;
    HecsCoord _location;  // Current loc or destination of current animation.
    float _heading;  // Current heading (or desination of current animation).

    public HexMovement() { }

    // Adds an animation to the queue.
    public void AddAnimation(IAnimation animation)
    {
        _animationQueue.Enqueue(animation);
    }

    // Is the object in the middle of an animation.
    public bool IsBusy()
    {
        return _animationQueue.Count == 0;
    }

    public float ImmediateHeading()
    { 
        if (IsBusy())
	    {
            return _animationQueue.Peek().Heading();
	    }
        return _heading;
    } 

    // The current location at this moment, including coordinates along the path
    // if the object is in an animation.
    public Vector3 ImmediateLocation()
    {
        // If we're animating, return the current animation location.
        if (IsBusy())
        {
            return _animationQueue.Peek().Location();
        }
        (float x, float z) = _location.Cartesian();
        // TODO(sharf): For supporting mountains, this will need to peek at the
        // GridManager to get the local Y-coordinate.
        return new Vector3(x, 0, z);
    }

    // Return the current animation type.
    public AnimationType ImmediateAnimation() { 
        if (IsBusy()) {
            return _animationQueue.Peek().Info().Type;
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
        // Fast-forward finished animations.
        while (_animationQueue.Count > 0 && _animationQueue.Peek().IsDone())
	    {
            _location = _animationQueue.Peek().Info().Destination;
            _animationQueue.Dequeue();
	    }

        if (_animationQueue.Count == 0) return;

        _animationQueue.Peek().Update();
    }
}
