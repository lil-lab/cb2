using System.Collections;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using UnityEngine;

public class GoogleOneTapLogin : MonoBehaviour
{
    public static string TAG = "GoogleOneTapLogin";
    // Javascript functions to render Google OneTap Login UI.
    [DllImport("__Internal")]
    private static extern void LoginGoogleOneTap(string client_id);
    // Only call after calling LoginGoogleOneTap()!
    [DllImport("__Internal")]
    private static extern void CancelGoogleOneTap();

    // The Google OAuth client ID.
    private static readonly string TESTING_CLIENT_ID = "787231947800-ee2g4lptmfa0av2qb26n1qu60hf5j2fd.apps.googleusercontent.com";
    private static readonly string REAL_CLIENT_ID = "787231947800-ee2g4lptmfa0av2qb26n1qu60hf5j2fd.apps.googleusercontent.com";

    private Logger _logger;

    public static GoogleOneTapLogin TaggedInstance()
    {
        GameObject obj = GameObject.FindGameObjectWithTag(GoogleOneTapLogin.TAG);
        if (obj == null)
            return null;
        return obj.GetComponent<GoogleOneTapLogin>();
    }

    // Start is called before the first frame update
    void Start()
    {
        _logger = Logger.GetOrCreateTrackedLogger("GoogleOneTapLogin");
    }

    private bool _loginDisplayed = false;

    public void ShowLoginUI()
    {
        if (_loginDisplayed) {
            _logger.Info("ShowLoginUI: Login already displayed.");
            return;
        } else {
            _logger.Info("Displaying UI.");
        }

        // Check URL Params. If there's no mturk ID, then show Google OneTap Login UI. 
        Dictionary<string, string> urlParameters = Network.NetworkManager.UrlParameters();
        if (urlParameters.ContainsKey("assignmentId"))
        {
            _logger.Info("Found mturk assignment ID. Not showing Google OneTap Login UI.");
            gameObject.SetActive(false);
            return;
        }

        // Only applies to WebGL contexts...
        if (Application.platform != RuntimePlatform.WebGLPlayer)
        {
            _logger.Info("Not WebGL. Not showing Google OneTap Login UI.");
            gameObject.SetActive(false);
            return;
        }

        // Depending on the URL, use the testing or real client ID.
        string client_id = REAL_CLIENT_ID;
        if (Application.absoluteURL.Contains("localhost"))
        {
            _logger.Info("Using testing client ID.");
            client_id = TESTING_CLIENT_ID;
        }

        // Show Google OneTap Login UI.
        _logger.Info("Showing Google OneTap Login UI with client ID: {client_id}");
        LoginGoogleOneTap(client_id);
        _loginDisplayed = true;
    }

    // On login callback from javascript plugin.
    public void OnLogin(string id_token)
    {
        _logger.Info("OnLogin() called with id_token: " + id_token);
        gameObject.SetActive(false);
        Network.NetworkManager.TaggedInstance().SetGoogleOauthToken(id_token);
    }

    public void CancelLoginUI()
    {
        _logger.Info("CancelLoginUI() called.");
        CancelGoogleOneTap();
        _loginDisplayed = false;
    }
}
