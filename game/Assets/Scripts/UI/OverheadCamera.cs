using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class OverheadCamera : MonoBehaviour
{
    public static readonly string TAG = "OverheadViewCam";

    public float Theta = 90;
    public float ScreenMargin = 0.05f;

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

    public void UpdateCamera()
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
}
