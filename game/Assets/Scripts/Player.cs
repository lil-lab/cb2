using System;
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

    public GameObject OverheadCamera;
    public GameObject AngledOverheadCamera;
    private Camera _fpvCamera;
    private DateTime _lastCameraToggle;
    private Network.TurnState _currentTurn;

    private int _playerId = -1;


    public void SetAssetId(int id)
    {
        UnityAssetSource assets = new UnityAssetSource();
        IAssetSource.AssetId assetId = (IAssetSource.AssetId)id;
        Actor actor = new Actor(assets.Load(assetId), assetId);
        if (_actor != null)
        {
            actor.AddAction(Init.InitAt(_actor.Location(), 0));
            _actor.Destroy();
        }
        _actor = actor;
        _actor.SetParent(gameObject);

        if (_network.Role() == Network.Role.LEADER)
        {
            _actor.SetScale(1.4f);
        } else {
            _actor.SetScale(1.8f);
        }

        GameObject cameraObj = _actor.Find("Parent/Main Camera");
        if (cameraObj != null)
        {
            _fpvCamera = cameraObj.GetComponent<Camera>();
        }
        InitCamera();
    }


    public void Awake()
    {
        UnityAssetSource assets = new UnityAssetSource();
        IAssetSource.AssetId assetId = IAssetSource.AssetId.PLAYER_WITH_CAM;
        _actor = new Actor(assets.Load(assetId), assetId);
        _actor.SetParent(gameObject);

        GameObject obj = GameObject.FindGameObjectWithTag(Network.NetworkManager.TAG);
        _network = obj.GetComponent<Network.NetworkManager>();

        if (_network.Role() == Network.Role.LEADER)
        {
            _actor.SetScale(1.4f);
        } else {
            _actor.SetScale(1.8f);
        }

        if (OverheadCamera == null)
        {
            Debug.Log("Error: No overhead camera provided.");
        }
    }

    void InitCamera()
    {
        GameObject cameraObj = _actor.Find("Parent/Main Camera");
        if (cameraObj != null)
        {
            _fpvCamera = cameraObj.GetComponent<Camera>();
        }
        if ((OverheadCamera != null) && (_network.Role() == Network.Role.LEADER))
        {
            if (_fpvCamera != null) _fpvCamera.enabled = false;
            OverheadCamera.GetComponent<Camera>().enabled = false;
            AngledOverheadCamera.GetComponent<Camera>().enabled = true;
        }
        _lastCameraToggle = DateTime.Now;
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
        InitCamera();
    }

    public void FlushActionQueue()
    {
        _actor.Flush();
    }

    public void AddAction(ActionQueue.IAction action)
    {
        _actor.AddAction(action);
    }
    public void HandleTurnState(Network.TurnState state)
    {
        _currentTurn = state;
    }

    // Actions are looped back from the server. This method is called to
    // validate actions. If an unrecognized action is received, then 
    // the client can request a state sync from the server.
    public void ValidateHistory(ActionQueue.IAction action)
    {
        // TODO(sharf): Implement this...
    }

    public Vector3 Position()
    {
        return _actor.Position();
    }

    public void SetPlayerId(int playerId) { _playerId = playerId; }
    public int PlayerId() { return _playerId; }

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

        if (CameraKey() &&
            (_network.Role() == Network.Role.LEADER) &&
            (OverheadCamera != null) &&
            (DateTime.Now - _lastCameraToggle).TotalMilliseconds > 500)
        {
            if (OverheadCamera.GetComponent<Camera>().enabled)
            {
                OverheadCamera.GetComponent<Camera>().enabled = false;
                AngledOverheadCamera.GetComponent<Camera>().enabled = true;
            }
            else
            {
                OverheadCamera.GetComponent<Camera>().enabled = true;
                AngledOverheadCamera.GetComponent<Camera>().enabled = false;
            }
            
            _lastCameraToggle = DateTime.Now;
        }

        // Don't move until we've received a TurnState.
        if (_currentTurn == null) return;


        // Ignore keypresses when it's not our turn.
        if (_currentTurn.turn != _network.Role())
        {
            return;
        }

        // Don't try to move if we're out of moves.
        if (_currentTurn.moves_remaining <= 0)
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

    private bool CameraKey()
    {
        bool keyboard = Input.GetKey(KeyCode.C);
        return keyboard;
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
