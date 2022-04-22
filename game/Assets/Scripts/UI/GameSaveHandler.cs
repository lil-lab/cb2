using System.Collections.Generic;
using UnityEngine;
using System.Runtime.InteropServices;

public class GameSaveHandler : MonoBehaviour
{
    [DllImport("__Internal")]
    private static extern void DownloadJson(string filename, string data);

    public void SaveGameData()
    {
        // Downloads the game's map update to a json file.
        Network.NetworkManager networkManager = Network.NetworkManager.TaggedInstance();
        IMapSource mapSource = networkManager.MapSource();
        if (mapSource == null)
        {
            Debug.Log("No map source.");
            return;
        }
        Network.MapUpdate mapUpdate = mapSource.RawMapUpdate();

        Network.BugReport localBugReport = new Network.BugReport();
        localBugReport.MapUpdate = mapUpdate;

        localBugReport.Logs = new List<Network.ModuleLog>();
        List<string> modules = Logger.GetTrackedModules();
        Debug.Log("Modules: " + modules.Count);
        foreach (string module in modules)
        {
            Logger logger = Logger.GetTrackedLogger(module);
            Network.ModuleLog moduleLog = new Network.ModuleLog();
            moduleLog.Module = module;
            moduleLog.Log = System.Text.Encoding.UTF8.GetString(logger.GetBuffer());
            localBugReport.Logs.Add(moduleLog);
            Debug.Log("Module: " + module + " and log size: " + moduleLog.Log.Length);
        }

        string bugReportJson = JsonUtility.ToJson(localBugReport, /*prettyPrint=*/true);
        DownloadJson("client_bug_report.json.log", bugReportJson);
    }
}
