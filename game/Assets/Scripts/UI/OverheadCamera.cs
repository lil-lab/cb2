using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;

public class OverheadCamera : MonoBehaviour
{
    public static readonly string OVERHEAD_TAG = "OverheadViewCam";
    public static readonly string ANGLED_TAG = "AngledViewCam";

    private static readonly float OrthographicPrecalculatedDistance = 200;

    public float Theta = 90;
    public float ScreenMargin = 0.05f;
    private float _calculatedDistance = 0;

    // If you assign a FollowPlayer instance, then the camera will center on the player with the provided distance.
    public GameObject FollowPlayer;
    public float FollowDistance = 10;
    public bool MousePanning = false;
    public float MousePanningSpeed = 0.01f;
    private Vector3 _mouseDragOrigin = Vector3.zero;
    private bool _isDraggingMouse = false;
    private float _phi = 0;  // the X-Z plane (Y-axis) rotation around the player. Controlled by the A and D keys.


    public static OverheadCamera TaggedOverheadInstance()
    {
        GameObject camera = GameObject.FindGameObjectWithTag(OVERHEAD_TAG);
        if (camera == null)
        {
            Debug.LogError("Could not find camera by tag: " + OVERHEAD_TAG);
            return null;
        }

        return camera.GetComponent<OverheadCamera>();
    }

    public static OverheadCamera TaggedAngledInstance()
    {
        GameObject camera = GameObject.FindGameObjectWithTag(ANGLED_TAG);
        if (camera == null)
        {
            Debug.LogError("Could not find camera by tag: " + ANGLED_TAG);
            return null;
        }

        return camera.GetComponent<OverheadCamera>();
    }
 
    public Camera GetCamera()
    {
        return gameObject.GetComponent<Camera>();
    }

    private bool IsPointClipped(Camera camera, Vector3 worldCoord, float margin, float clipMargin=1.0f)
    {
        Vector3 viewPortPoint = camera.WorldToViewportPoint(worldCoord);
        return (viewPortPoint.x < margin) || (viewPortPoint.x > 1 - margin) ||
               (viewPortPoint.y < margin) || (viewPortPoint.y > 1 - margin) || (viewPortPoint.z < (camera.nearClipPlane + clipMargin)) || (viewPortPoint.z > (camera.farClipPlane - clipMargin));
    }
    
    private void AdjustDepthIfClipped(Camera camera, float clipMargin=1.0f)
    {
        if (camera.orthographic)
        {
            _calculatedDistance = OrthographicPrecalculatedDistance;
            return;
        }
        HexGrid grid = HexGrid.TaggedInstance();
        (int rows, int cols) = grid.MapDimensions();
        if ((rows == 0) || (cols == 0))
        {
            Debug.Log("Grid not yet initialized. Returning.");
            _calculatedDistance = 50;
            return;
        }
        List<Vector3> corners = new List<Vector3>();
        corners.Add(grid.Position(0, 0));
        corners.Add(grid.Position(rows - 1, 0));
        corners.Add(grid.Position(0, cols - 1));
        corners.Add(grid.Position(rows - 1, cols - 1));
        bool clipped = false;
        foreach (Vector3 corner in corners)
        {
            if (IsPointClipped(GetCamera(), corner, ScreenMargin))
            {
                clipped = true;
                break;
            }
        }
        if (clipped)
        {
            _calculatedDistance += Time.deltaTime * 10f;
        }
    }

    public void CenterCameraOnGrid()
    {
        if (GetCamera().orthographic)
        {
            _calculatedDistance = OrthographicPrecalculatedDistance;
            return;
        }
        HexGrid grid = HexGrid.TaggedInstance();
        Vector3 center = grid.CenterPosition();
        (int rows, int cols) = grid.MapDimensions();
        Debug.Log(rows + ", " + cols);
        if ((rows == 0) || (cols == 0))
        {
            Debug.Log("Grid not yet initialized. Returning.");
            _calculatedDistance = 50;
            return;
        }
        transform.rotation = Quaternion.Euler(Theta, 90, 0);
        float distance = 10;
        float thetaRadians = Theta * Mathf.Deg2Rad;
        transform.position = new Vector3(
                center.x - distance * Mathf.Cos(thetaRadians), 
                center.y + distance * Mathf.Sin(thetaRadians),
                center.z);
        for (int i = 0; i < 200; ++i)
        {
            List<Vector3> corners = new List<Vector3>();
            corners.Add(grid.Position(0, 0));
            corners.Add(grid.Position(rows - 1, 0));
            corners.Add(grid.Position(0, cols - 1));
            corners.Add(grid.Position(rows - 1, cols - 1));
            bool clipped = false;
            foreach (Vector3 corner in corners)
            {
                if (IsPointClipped(GetCamera(), corner, ScreenMargin))
                {
                    clipped = true;
                    break;
                }
            }
            if (clipped)
            {
                distance += 1;
                transform.position = new Vector3(
                    center.x - distance * Mathf.Cos(thetaRadians) * Mathf.Cos(_phi), 
                    center.y + distance * Mathf.Sin(thetaRadians),
                    center.z + distance * Mathf.Cos(thetaRadians) * Mathf.Sin(_phi));
            }
            else
            {
                Debug.Log(transform.position);
                _calculatedDistance = distance;
                return;
            }
        }
        _calculatedDistance = distance;
        Debug.Log("Unable to satisfy camera constraints after 100 iterations");
    }

    public void Update()
    {
        if (GetCamera() == null)
        {
            Debug.LogError("Camera is null");
            return;
        }

        // When a UI element is selected, ignore keypresses. This prevents the
        // camera from moving when the user is typing and hits W/A/S/D.
        if (EventSystem.current.currentSelectedGameObject != null)
        {
            return;
        }
        // When the camera is disabled, ignore inputs and don't run camera calculations.
        if (!GetCamera().enabled)
        {
            return;
        }

        if (Input.GetKey(KeyCode.A))
        {
            _phi += Time.deltaTime;
        }
        if (Input.GetKey(KeyCode.D))
        {
            _phi -= Time.deltaTime;
        }
        if (MousePanning)
        {
            if (Input.GetMouseButtonDown(0))
            {
                _mouseDragOrigin = Input.mousePosition;
                _isDraggingMouse = true;
            }
            if (!Input.GetMouseButton(0) || Input.GetMouseButtonUp(0))
            {
                _isDraggingMouse = false;
            }
            if (_isDraggingMouse)
            {
                Vector3 delta = Input.mousePosition - _mouseDragOrigin;
                _mouseDragOrigin = Input.mousePosition;
                _phi += delta.x * MousePanningSpeed * Time.deltaTime;
            }
        } else
        {
            _isDraggingMouse = false;
        }
        HexGrid grid = HexGrid.TaggedInstance();
        Vector3 center = (FollowPlayer != null) ? FollowPlayer.GetComponent<Player>().Position() : grid.CenterPosition();
        float distance = (FollowPlayer != null) ? FollowDistance : _calculatedDistance;
        float thetaRadians = Theta * Mathf.Deg2Rad;
        transform.position = new Vector3(
            center.x - distance * Mathf.Cos(thetaRadians) * Mathf.Cos(_phi), 
            center.y + distance * Mathf.Sin(thetaRadians),
            center.z + distance * Mathf.Cos(thetaRadians) * Mathf.Sin(_phi));
        transform.rotation = Quaternion.Euler(Theta, _phi * Mathf.Rad2Deg + 90, 0);
    }
}
