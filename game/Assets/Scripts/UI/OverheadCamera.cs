using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class OverheadCamera : MonoBehaviour
{
    public static readonly string TAG = "OverheadViewCam";

    public float Theta = 90;
    public float ScreenMargin = 0.05f;

    // If you assign a FollowPlayer instance, then the camera will center on the player with the provided distance.
    public GameObject FollowPlayer;
    public float FollowDistance = 10;
    private float phi = 90;  // the X-Z plane (Y-axis) rotation around the player. Controlled by the A and D keys.

    public static OverheadCamera TaggedInstance()
    {
        GameObject camera = GameObject.FindGameObjectWithTag(TAG);
        if (camera == null)
        {
            Debug.LogError("Could not find camera by tag: " + TAG);
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
            "C: Toggle between Cameras.";
    }

    public void CenterCameraOnGrid()
    {
        HexGrid grid = HexGrid.TaggedInstance();
        Vector3 center = grid.CenterPosition();
        (int rows, int cols) = grid.MapDimensions();
        transform.rotation = Quaternion.Euler(Theta, 90, 0);
        float distance = 10;
        float thetaRadians = Theta * Mathf.Deg2Rad;
        transform.position = new Vector3(
                center.x - distance * Mathf.Cos(thetaRadians), 
                center.y + distance * Mathf.Sin(thetaRadians),
                center.z);
        for (int i = 0; i < 100; ++i)
        {
            Vector3 corner = grid.Position(0, 0);
            Vector3 otherCorner = grid.Position(rows-1, cols-1);
            Vector3 screenPoint = GetCamera().WorldToScreenPoint(corner);
            Vector3 otherScreenPoint = GetCamera().WorldToScreenPoint(otherCorner);
            Debug.Log(screenPoint + " " + otherScreenPoint + " " + distance);
            float ScreenHeightMargin = Screen.height * ScreenMargin;
            (float, float) ScreenHeightRange = (ScreenHeightMargin, Screen.height - ScreenHeightMargin);
            float ScreenWidthMargin = Screen.width * ScreenMargin;
            (float, float) ScreenWidthRange = (ScreenWidthMargin, Screen.width - ScreenWidthMargin);
            if (screenPoint.x < ScreenWidthRange.Item1 ||
                screenPoint.y < ScreenHeightRange.Item1 ||
                otherScreenPoint.x > ScreenWidthRange.Item2 ||
                otherScreenPoint.y > ScreenHeightRange.Item2)
            {
                distance += 1;
                transform.position = new Vector3(
                    center.x - distance * Mathf.Cos(thetaRadians), 
                    center.y + distance * Mathf.Sin(thetaRadians),
                    center.z);
            }
            else
            {
                Debug.Log(transform.position);
                return;
            }
        }
        Debug.Log("Unable to satisfy camera constraints after 100 iterations");
    }

    public void Update()
    {
        if (FollowPlayer != null)
        {
            Player target = FollowPlayer.GetComponent<Player>();
            Vector3 center = target.Position();
            float thetaRadians = Theta * Mathf.Deg2Rad;
            transform.rotation = Quaternion.Euler(Theta, phi * Mathf.Rad2Deg + 90, 0);
            transform.position = new Vector3(
                    center.x - FollowDistance * Mathf.Cos(thetaRadians) * Mathf.Cos(phi), 
                    center.y + FollowDistance * Mathf.Sin(thetaRadians),
                    center.z + FollowDistance * Mathf.Cos(thetaRadians) * Mathf.Sin(phi));
            if (GetCamera() != null)
            {
                if (Input.GetKey(KeyCode.A))
                {
                    phi += Time.deltaTime;
                }
                if (Input.GetKey(KeyCode.D))
                {
                    phi -= Time.deltaTime;
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
