using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;

public class Player : MonoBehaviour
{
    public static string TAG = "Player";

    public float TurnSpeed = 2;  // Turns/Second.
    public float MoveSpeed = 0.2f;  // Cells/Second.

    public bool ForceStartingPosition = false;
    public int StartingRow = 9;
    public int StartingCol = 7;
    public bool ShowHeading = true;

    private Network.NetworkManager _network;

    private Actor _actor;

    public void Awake()
    {
        UnityAssetSource assets = new UnityAssetSource();
        _actor = new Actor(assets.Load(IAssetSource.AssetId.PLAYER_WITH_CAM));
        _actor.SetParent(gameObject);

        GameObject obj = GameObject.FindGameObjectWithTag(Network.NetworkManager.TAG);
        _network = obj.GetComponent<Network.NetworkManager>();
    }

    void Start()
    {
        if (ForceStartingPosition)
        {
            _actor.AddAction(
                Init.InitAt(
                    HecsCoord.FromOffsetCoordinates(StartingRow,
                                                    StartingCol), 0));
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

    // Actions are looped back from the server. This method is called to
    // validate actions. If an unrecognized action is received, then 
    // the client can request a state sync from the server.
    public void ValidateHistory(ActionQueue.IAction action)
    {
        // TODO(sharf): Implement this...
    }

    void Update()
    {
        if (ShowHeading)
        {
            _actor.EnableDebugging();
        }
        else
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

        // When a UI element is selected, ignore keypresses. This prevents the
        // player from moving when the user is typing and hits the left or right
        // keys to move the cursor.
        if (EventSystem.current.currentSelectedGameObject != null)
        {
            return;
        }

        if (UpKey() &&
            !grid.EdgeBetween(_actor.Location(), forwardLocation))
        {
            Translate action = Translate.Walk(
                HecsCoord.ORIGIN.NeighborAtHeading(_actor.HeadingDegrees()),
                                                   1 / MoveSpeed);
            _actor.AddAction(action);
            _network.TransmitAction(action);
            return;
        }
        if (DownKey() &&
            !grid.EdgeBetween(_actor.Location(), backLocation))
        {
            Translate action = Translate.Walk(
                HecsCoord.ORIGIN.NeighborAtHeading(
                    _actor.HeadingDegrees() + 180), 1 / MoveSpeed);
            _actor.AddAction(action);
            _network.TransmitAction(action);
            return;
        }
        if (LeftKey())
        {
            Debug.Log("Heading: " + (_actor.HeadingDegrees() - 60.0f));
            Rotate action = Rotate.Turn(-60.0f, 1 / TurnSpeed);
            _actor.AddAction(action);
            _network.TransmitAction(action);
            return;
        }
        if (RightKey())
        {
            Rotate action = Rotate.Turn(60.0f, 1 / TurnSpeed);
            _actor.AddAction(action);
            _network.TransmitAction(action);
            return;
        }
    }

    private bool UpKey()
    {
        bool keyboard = Input.GetKey(KeyCode.UpArrow);
        // bool gamepad = Input.GetAxis("Axis 6") < -0.2;
        // bool gamepad_dpad = Input.GetAxis("Axis 10") < -0.2;
        return keyboard;  // || gamepad || gamepad_dpad;
    }

    private bool DownKey()
    {
        bool keyboard = Input.GetKey(KeyCode.DownArrow);
        // bool gamepad = Input.GetAxis("Axis 6") > 0.2;
        // bool gamepad_dpad = Input.GetAxis("Axis 10") > 0.2;
        return keyboard;  // || gamepad || gamepad_dpad;
    }

    private bool LeftKey()
    {
        bool keyboard = Input.GetKey(KeyCode.LeftArrow);
        // bool gamepad = Input.GetAxis("Axis 5") < -0.2;
        // bool gamepad_dpad = Input.GetAxis("Axis 9") < -0.2;
        return keyboard; // || gamepad || gamepad_dpad;
    }

    private bool RightKey()
    {
        bool keyboard = Input.GetKey(KeyCode.RightArrow);
        // bool gamepad = Input.GetAxis("Axis 5") > 0.2;
        // bool gamepad_dpad = Input.GetAxis("Axis 9") > 0.2;
        return keyboard;  // || gamepad || gamepad_dpad;
    }

    private float Scale()
    {
        GameObject obj = GameObject.FindWithTag(HexGrid.TAG);
        HexGrid manager = obj.GetComponent<HexGrid>();
        return manager.Scale;
    }
}
