using System;
using System.Collections.Generic;
using UnityEngine;


// This class is a queue of actions that some object shall take. Custom actions 
// can be implemented via the IAction interface and each action can be
// associated with its own animation type.

// This is generally used to animate game objects, however it is also repurposed for UI animation.
public class ActionQueue
{
    [Serializable]
    public enum AnimationType
    {
        NONE,
        IDLE,
        WALKING,
        INSTANT,
        TRANSLATE,
        ACCEL_DECEL,
        SKIPPING,
        ROTATE,
        FADE,
    }

    public class ActionInfo
    {
        public AnimationType Type;
        public HecsCoord Displacement;  // Object displacement in HECS coords.
        public float Rotation;  // Heading in degrees, 0 = north, clockwise.
        public float BorderRadius;  // Radius of the object's outline, if applicable.
        public float Opacity;  // Used for UI element animations.
        public float DurationS;  // Duration in seconds.
        public DateTime Expiration;  // If the action delays past this deadline, fastforward to next action.
    };

    // A kind of action (walk, skip, jump). This is distinctly different from 
    // the model animation (though related).  The action defines how an object
    // moves through space as a function of time. The animation defines how the
    // object mesh changes (leg action motion, etc) as the object moves.
    public interface IAction
    {
        // Calculate intermediate state, given initial conditions and progress.
        // 
        // progress represents the action's completion (1.0 = completely done).
        State.Continuous Interpolate(State.Discrete initialConditions,
                                     float progress);
        // Calculate the next state, given the current state and an action.
        State.Discrete Transfer(State.Discrete s);
        // Action's duration in seconds.
        float DurationS();
        // Action's expiration date in system time.
        DateTime Expiration();
        // Convert this action to a packet that can be sent over the network.
        Network.Action Packet(int id);
    }

    private Queue<IAction> _actionQueue;
    private State.Discrete _state;
    private State.Discrete _targetState;
    private bool _actionInProgress;
    private DateTime _actionStarted;
    private float _progress;  // Progress of the current action. 0 -> 1.0f.
    private HexGrid _grid;

    public ActionQueue()
    {
        _actionQueue = new Queue<IAction>();
        _actionInProgress = false;
        _state = new State.Discrete();
        _targetState = new State.Discrete();
    }

    // Adds a move to the queue.
    public void AddAction(IAction action)
    {
        if (action == null)
        {
            return;
        }
        _targetState = action.Transfer(_targetState);
        _actionQueue.Enqueue(action);
    }

    // Is the object in the middle of a action.
    public bool IsBusy()
    {
        return _actionInProgress;
    }

    public int PendingActions()
    {
        return _actionQueue.Count;
    }

    public State.Continuous ContinuousState()
    {
        if (IsBusy())
        {
            return _actionQueue.Peek().Interpolate(_state, _progress);
        }
        return _state.Continuous();
    }

    public State.Discrete State()
    {
        return _state;
    }

    public State.Discrete TargetState()
    {
        return _targetState;
    }

    // Wipe all current actions.
    public void Flush()
    {
        _actionQueue.Clear();
        _actionInProgress = false;
        _progress = 0.0f;
        _targetState = _state;
    }

    public void Update()
    {
        // If there's no animation in progress, begin the next animation in the queue.
        if (_actionQueue.Count > 0 && !_actionInProgress)
        {
            _progress = 0.0f;
            _actionStarted = DateTime.Now;
            _actionInProgress = true;
        }

        // Immediately skip any expired animations.
        if (_actionInProgress && (DateTime.Now > _actionQueue.Peek().Expiration()))
        {
            Debug.Log("Fast-forwarding expired action");
            _state = _actionQueue.Peek().Transfer(_state);
            _actionQueue.Dequeue();
            _actionInProgress = false;
        }

        TimeSpan delta = DateTime.Now - _actionStarted;

        // Convert to milliseconds for higher-resolution progress.
        if (_actionInProgress)
        {
            _progress = ((delta).Milliseconds) /
                        (_actionQueue.Peek().DurationS() * 1000.0f);
        }

        // End the current action when progress >= 1.0.
        if (_actionInProgress &&
            (delta.Milliseconds > (_actionQueue.Peek().DurationS() * 1000.0f)))
        {
            _state = _actionQueue.Peek().Transfer(_state);
            _actionQueue.Dequeue();
            _actionInProgress = false;
        }
    }

}
