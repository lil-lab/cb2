using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class ShowCardCovers : MonoBehaviour
{
    private bool _cardCoversSet = false;
    private DateTime _lastTry = DateTime.MinValue;
    private Logger _logger;
    // Start is called before the first frame update
    void Start()
    {
        _logger = Logger.GetOrCreateTrackedLogger("ShowCardCovers");
    }

    public void Update()
    {
        if (_cardCoversSet) return;
        // Try this every 3 seconds.
        if (DateTime.Now - _lastTry < TimeSpan.FromSeconds(3)) return;

        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();
        if (networkManager.ServerConfig() == null) return;

        Camera camera = GetComponent<Camera>();
        if (networkManager.ServerConfig().card_covers)
        {
            camera.cullingMask = camera.cullingMask | (1 << LayerMask.NameToLayer("card_covers"));
        } else {
            camera.cullingMask = camera.cullingMask & ~(1 << LayerMask.NameToLayer("card_covers"));
        }
        _logger.Info("Set card covers to " + networkManager.ServerConfig().card_covers);
        _cardCoversSet = true;
    }
}