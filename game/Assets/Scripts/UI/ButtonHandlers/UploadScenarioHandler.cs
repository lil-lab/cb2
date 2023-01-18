using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System.Runtime.InteropServices;
using Newtonsoft.Json;

public class UploadScenarioHandler : MonoBehaviour, IPointerUpHandler
{

    [DllImport("__Internal")]
    private static extern void PromptUpload();

    public void OnPointerUp(PointerEventData eventData)
    {
        // Call into javascript file picker plugin.
        PromptUpload();
    }

    // On file ready callback from javascript plugin.
    public void OnFileReady(string contents)
    {
        // Attempt to parse the file as a JSON Scenario.
        Network.Scenario scenario = JsonConvert.DeserializeObject<Network.Scenario>(contents);
        Network.ScenarioRequest request = new Network.ScenarioRequest();
        request.type = Network.ScenarioRequestType.LOAD_SCENARIO;
        request.scenario_data = scenario;
        Network.NetworkManager.TaggedInstance().TransmitScenarioRequest(request);
    }
}
