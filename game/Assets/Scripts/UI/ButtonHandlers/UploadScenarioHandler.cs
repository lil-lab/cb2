using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System.Runtime.InteropServices;
using Newtonsoft.Json;

public class UploadScenarioHandler : MonoBehaviour, IPointerUpHandler
{
    private Logger _logger;
    public void Start()
    {
        _logger = Logger.GetOrCreateTrackedLogger("UploadScenarioHandler");
    }

    // Calls into javascript file picker plugin.
    [DllImport("__Internal")]
    private static extern void PromptUpload();

    public void OnPointerUp(PointerEventData eventData)
    {
        // Callback handled in ScenarioUploadReceiver gameobject.
        MenuTransitionHandler.TaggedInstance().AskForAFile(UploadScenarioHandler.OnFileReady);
    }

    public static void OnFileReady(string contents)
    {
        // Attempt to parse the file as a JSON Scenario.
        Logger.GetOrCreateTrackedLogger("UploadScenarioHandler").Info("OnFileReady: Transmitting scenario file.");
        Network.ScenarioRequest request = new Network.ScenarioRequest();
        request.type = Network.ScenarioRequestType.LOAD_SCENARIO;
        request.scenario_data = contents;
        Network.NetworkManager.TaggedInstance().TransmitScenarioRequest(request);
    }    
}