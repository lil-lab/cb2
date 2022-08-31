using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ShowLiveFeedback : MonoBehaviour
{
    private bool _liveFeedbackSet = false;
    private DateTime _lastTry = DateTime.MinValue;
    private Logger _logger;
    // Start is called before the first frame update
    void Start()
    {
        _logger = Logger.GetOrCreateTrackedLogger("ShowLiveFeedback");
        _lastTry = DateTime.MinValue;
    }

    public void Update()
    {
        if (_liveFeedbackSet) return;
        // Try this every 3 seconds.
        if (DateTime.Now - _lastTry < TimeSpan.FromSeconds(3)) return;

        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();
        if (networkManager.ServerConfig() == null) return;

        Camera camera = GetComponent<Camera>();
        // Only disable live feedback if its not configured. It should be shown
        // by-default, so we don't need to enable it. Other components might
        // disable it, and this would nullify their effect (e.g. feedback
        // buttons aren't shown to the follower. Don't want to override that by
        // accident here and show them).
        if (!networkManager.ServerConfig().live_feedback_enabled)
        {
            gameObject.SetActive(false);
        }
        _logger.Info("Set live feedback to: " + networkManager.ServerConfig().live_feedback_enabled);
        _liveFeedbackSet = true;
    }
}