using System;
using System.Collections.Generic;
using UnityEngine;


// This class is a queue of actions that some object shall take. Custom actions 
// can be implemented via the IAction interface and each action can be
// associated with its own animation type.
public class ActionQueue
{
    [Serializable]
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

    public class ActionInfo
    {
        public AnimationType Type;
        public HecsCoord Start;  // Where the move starts from.
        public HecsCoord Destination;  // Where the object should end up.
        public float StartHeading;  // Heading in degrees, 0 = north, clockwise around.
        public float DestinationHeading;  // Heading, 0 = north, clockwise.
        public float DurationS;  // Duration in seconds.
        public DateTime Expiration;  // If the action delays past this deadline, fastforward to next action.
    };

    // A kind of action (walk, skip, jump). This is distinctly different from 
    // the model animation (though related).  The action defines how an object
    // moves through space as a function of time. The animation defines how the
    // object mesh changes (leg action motion, etc) as the object moves.
    public interface IAction
    {
        void Start();
        ActionInfo Info();
        void Update();
        Vector3 Location();
        float Heading();
        bool IsDone();
    }

    private Queue<IAction> _actionQueue;
    private HecsCoord _location;  // Current loc or destination of current action.
    private float _heading;  // Current heading (or desination of current action).
    private bool _actionInProgress;
    private HexGrid _grid;

    public ActionQueue()
    {
        _actionQueue = new Queue<IAction>();
        _actionInProgress = false;
        _location = new HecsCoord(0, 0, 0);
    }

    // Adds a move to the queue.
    public void AddAction(IAction action)
    {
        if (action == null)
	    {
            return;
	    }
        _actionQueue.Enqueue(action);
    }

    // Is the object in the middle of a action.
    public bool IsBusy()
    {
        return _actionQueue.Count != 0;
    }

    public float ImmediateHeading()
    { 
        if (IsBusy())
	    {
            return _actionQueue.Peek().Heading();
	    }
        return _heading;
    } 

    // The current location at this moment, including coordinates along the path
    // if the object is moving.
    public Vector3 ImmediateLocation()
    {
        // If we're moving, return the current action location.
        if (IsBusy())
        {
            return _actionQueue.Peek().Location();
        }
        (float x, float z) = _location.Cartesian();

        // Fetch a reference to the grid for the height map.
        GameObject obj = GameObject.FindGameObjectWithTag(HexGrid.TAG);
        if (obj != null)
        {
            Debug.Log("ActionQueue could not find grid tagged with: " + HexGrid.TAG);
            return new Vector3(x, 0, z);
        }

        _grid = obj.GetComponent<HexGrid>();
        return new Vector3(x, _grid.Height(_location), z);
    }

    // Return the current animation type.
    public AnimationType ImmediateAnimation() { 
        if (IsBusy()) {
            return _actionQueue.Peek().Info().Type;
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

    // Wipe all current actions.
    public void Flush()
    {
        _actionQueue.Clear(); 
    }

    public void Update()
    { 
        // If there's no animation in progress, begin the next animation in the queue.
        if (_actionQueue.Count > 0 && !_actionInProgress) {
            _actionQueue.Peek().Start();
            _actionInProgress = true;
	    }

        // Flush any finished animations.
        while (_actionQueue.Count > 0 && _actionQueue.Peek().IsDone())
	    {
            // Even if we're fast-forwarding through an expired animation, the
	        // resulting location/heading should be kept.
            _location = _actionQueue.Peek().Info().Destination;
            _heading = _actionQueue.Peek().Info().DestinationHeading;
            _actionQueue.Dequeue();
            _actionInProgress = false;
	    }

        if (_actionQueue.Count == 0) return;

        if (_actionInProgress)
		    _actionQueue.Peek().Update();
    }
}
