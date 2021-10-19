using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Player : MonoBehaviour
{
    public static string TAG = "Player";

    public float TurnSpeed = 2;  // Turns/Second.
    public float MoveSpeed = 0.2f;  // Cells/Second.

    public bool ForceStartingPosition = false;
    public int StartingRow = 9;
    public int StartingCol = 7;
    public bool ShowHeading = false;

    private Network.NetworkManager _network;

    private Actor _actor;

    public void Awake()
    {
        UnityAssetSource assets = new UnityAssetSource(); 
        _actor = new Actor(assets.Load(IAssetSource.AssetId.PLAYER));
        _actor.SetParent(gameObject);

        GameObject obj = GameObject.FindGameObjectWithTag(Network.NetworkManager.TAG);
        _network = obj.GetComponent<Network.NetworkManager>();
    }

    void Start()
    {
	    if (ForceStartingPosition)
	    {
	       	 // Set the starting location by enqueuing a teleport to the target location.
	       	 var startingLocation = new ActionQueue.ActionInfo
	       	 {
	       	     Type = ActionQueue.AnimationType.INSTANT,
	       	     Destination = HecsCoord.FromOffsetCoordinates(StartingRow, StartingCol),
	       	     DestinationHeading = 0
	       	 };
	       	 _actor.AddAction(new Instant(startingLocation));
	    }
    }

    public void FlushActionQueue()
    {
        _actor.Flush();
    }

    public void AddAction(ActionQueue.IAction action)
    {
        _actor.AddAction(action); 
    }

    void Update()
    {
        if (ShowHeading)
        {
            _actor.EnableDebugging();
	    } else
	    {
            _actor.DisableDebugging();
	    }

        _actor.Update();

        // If we're doing an action, don't check for user input.
        if (_actor.IsBusy()) return;

        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        HexGrid grid = obj.GetComponent<HexGrid>();

        HecsCoord forwardLocation = _actor.Location().NeighborAtHeading(_actor.HeadingDegrees());
        HecsCoord backLocation = _actor.Location().NeighborAtHeading(_actor.HeadingDegrees() + 180);

        if (Input.GetKey(KeyCode.UpArrow) &&
	        !grid.EdgeBetween(_actor.Location(), forwardLocation))
        { 
            var animationInfo = new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.WALKING,
                Destination = forwardLocation,
                DestinationHeading = _actor.HeadingDegrees(),
                Start = _actor.Location(),
                StartHeading = _actor.HeadingDegrees(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / MoveSpeed,
            };
            Translate action = new Translate(animationInfo);
            _actor.AddAction(action);
            _network.TransmitAction(action);
            return;
	    }
        if (Input.GetKey(KeyCode.DownArrow) &&
	        !grid.EdgeBetween(_actor.Location(), backLocation))
        { 
            var animationInfo = new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.WALKING,
                Destination = backLocation,
                DestinationHeading = _actor.HeadingDegrees(),
                Start = _actor.Location(),
                StartHeading = _actor.HeadingDegrees(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / MoveSpeed,
            };
            Translate action = new Translate(animationInfo);
            _actor.AddAction(action);
            _network.TransmitAction(action);
            return;
	    }
        if (Input.GetKey(KeyCode.LeftArrow))
        {
            var animationInfo = new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.ROTATE,
                Destination = _actor.Location(),
                DestinationHeading = _actor.HeadingDegrees() - 60.0f,
                Start = _actor.Location(),
                StartHeading = _actor.HeadingDegrees(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / TurnSpeed,
            };
            Rotate action = new Rotate(animationInfo);
            _actor.AddAction(action);
            _network.TransmitAction(action);
            return;
	    }
        if (Input.GetKey(KeyCode.RightArrow))
        {
            var animationInfo = new ActionQueue.ActionInfo()
            {
                Type = ActionQueue.AnimationType.ROTATE,
                Destination = _actor.Location(),
                DestinationHeading = _actor.HeadingDegrees() + 60.0f,
                Start = _actor.Location(),
                StartHeading = _actor.HeadingDegrees(),
                Expiration = System.DateTime.Now.AddSeconds(10),
                DurationS = 1 / TurnSpeed,
            };
            Rotate action = new Rotate(animationInfo);
            _actor.AddAction(action);
            _network.TransmitAction(action);
            return;
	    }
    }

    private float Scale()
    {
        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        HexGrid manager = obj.GetComponent<HexGrid>();
        return manager.Scale;
    }
}
