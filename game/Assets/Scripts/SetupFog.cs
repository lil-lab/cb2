using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class SetupFog : MonoBehaviour
{
    private bool fogInitialized = false;
    private Logger _logger;
    // Start is called before the first frame update
    void Start()
    {
        _logger = Logger.GetOrCreateTrackedLogger("SetupFog");
        fogInitialized = false;
    }

    // Update is called once per frame
    void Update()
    {
        if (!fogInitialized)
        {
            Network.Config cfg = Network.NetworkManager.TaggedInstance().ServerConfig();
            if (cfg != null)
            {
                RenderSettings.fogStartDistance = cfg.fog_start;
                RenderSettings.fogEndDistance = cfg.fog_end;
                _logger.Info("Fog initialized with start: " + cfg.fog_start + " and end: " + cfg.fog_end);
                fogInitialized = true;
            }
        }
    }
}
