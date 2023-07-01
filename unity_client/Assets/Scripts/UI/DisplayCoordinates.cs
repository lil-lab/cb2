using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI; 

public class DisplayCoordinates : MonoBehaviour
{
    private Logger _logger;

    public static DisplayCoordinates GetInstance()
    {
        return GameObject.FindWithTag("DisplayCoordinates").GetComponent<DisplayCoordinates>();
    }

    public void Awake()
    {
        _logger = Logger.GetOrCreateTrackedLogger("DisplayCoordinates");
    }

    public void ToggleDisplay()
    {
        // Get the top level canvas group.
        CanvasGroup canvasGroup = GetComponentInParent<CanvasGroup>();
        if (canvasGroup == null)
        {
            _logger.Warn("DisplayCoordinates.ToggleDisplay(): Could not find CanvasGroup");
            return;
        }
        // If the alpha is 0, make it 1. If it's 1, make it 0.
        canvasGroup.alpha = canvasGroup.alpha == 0 ? 1 : 0;
    }

    // Update is called once per frame
    void Update()
    {
        Player p = Player.TaggedInstance();
        if (p == null) return;

        HecsCoord location = p.Coordinate();

        HecsCoord forwardLocation = location.NeighborAtHeading(p.HeadingDegrees());
        HecsCoord backLocation = location.NeighborAtHeading(p.HeadingDegrees() + 180);

        // Format the coordinates in a fixed-length string like "Forward: (a, r, c) | On: (a, r, c) | Back: (a, r, c)"
        string coordinates = string.Format("Front: {0} | On: {1} | Back: {2}", forwardLocation, location, backLocation);

        // Display the coordinates in the game window
        Text t = GetComponent<Text>();
        t.text = coordinates;
    }
}