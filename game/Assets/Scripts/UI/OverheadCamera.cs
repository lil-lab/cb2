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

    public string CameraInstructions()
    {
        if (FollowPlayer != null) {
            return "Camera Instructions:\n" +
                "W/A/S/D: Move Camera.\n" +
                "C: Toggle between Cameras.";
        }

        return "Camera Instructions:\n" +
            "A/D: Rotate Camera.\n" +
            "C: Toggle between Cameras.";
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
        if (GetCamera() != null)
        {
            // When a UI element is selected, ignore keypresses. This prevents the
            // camera from moving when the user is typing and hits W/A/S/D.
            if (EventSystem.current.currentSelectedGameObject != null)
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
            HexGrid grid = HexGrid.TaggedInstance();
            Vector3 center = grid.CenterPosition();
            float thetaRadians = Theta * Mathf.Deg2Rad;
            transform.position = new Vector3(
                center.x - _calculatedDistance * Mathf.Cos(thetaRadians) * Mathf.Cos(_phi), 
                center.y + _calculatedDistance * Mathf.Sin(thetaRadians),
                center.z + _calculatedDistance * Mathf.Cos(thetaRadians) * Mathf.Sin(_phi));
            transform.rotation = Quaternion.Euler(Theta, _phi * Mathf.Rad2Deg + 90, 0);
            Debug.Log(_calculatedDistance);
        }
        if (FollowPlayer != null)
        {
            Player target = FollowPlayer.GetComponent<Player>();
            Vector3 center = target.Position();
            float thetaRadians = Theta * Mathf.Deg2Rad;
            transform.rotation = Quaternion.Euler(Theta, _phi * Mathf.Rad2Deg + 90, 0);
            transform.position = new Vector3(
                    center.x - FollowDistance * Mathf.Cos(thetaRadians) * Mathf.Cos(_phi), 
                    center.y + FollowDistance * Mathf.Sin(thetaRadians),
                    center.z + FollowDistance * Mathf.Cos(thetaRadians) * Mathf.Sin(_phi));
            if (GetCamera() != null)
            {
                // When a UI element is selected, ignore keypresses. This prevents the
                // camera from moving when the user is typing and hits W/A/S/D.
                if (EventSystem.current.currentSelectedGameObject != null)
                {
                    return;
                }
                if (Input.GetKey(KeyCode.W))
                {
                    FollowDistance -= 4 * Time.deltaTime;
                }
                if (Input.GetKey(KeyCode.S))
                {
                    FollowDistance += 4 * Time.deltaTime;
                }
            }
        }
    }
}
