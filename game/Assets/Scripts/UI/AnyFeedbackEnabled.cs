using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;


public class AnyFeedbackEnabled : MonoBehaviour
{
    private bool _FeedbackSet = false;
    private DateTime _lastTry = DateTime.MinValue;
    private Logger _logger;
    // Start is called before the first frame update
    void Start()
    {
        _logger = Logger.GetOrCreateTrackedLogger("AnyFeedbackEnabled");
        _lastTry = DateTime.MinValue;
    }

    public void Update()
    {
        if (_FeedbackSet) return;
        // Try this every 3 seconds.
        if (DateTime.Now - _lastTry < TimeSpan.FromSeconds(3)) return;

        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();
        if (networkManager.ServerLobbyInfo() == null) return;

        Camera camera = GetComponent<Camera>();
        // Only disable feedback if its not configured. It should be shown
        // by-default, so we don't need to enable it. Other components might
        // disable it, and this would nullify their effect (e.g. feedback
        // buttons aren't shown to the follower. Don't want to override that by
        // accident here and show them).
        bool config_enabled = (networkManager.ServerConfig().live_feedback_enabled || 
                               networkManager.ServerLobbyInfo().live_feedback_enabled ||
                               networkManager.ServerLobbyInfo().delayed_feedback_enabled);
        if (!config_enabled)
        {
            gameObject.SetActive(false);
        }
        _logger.Info("Set (any) feedback to: " + config_enabled);
        _FeedbackSet = true;
    }
}