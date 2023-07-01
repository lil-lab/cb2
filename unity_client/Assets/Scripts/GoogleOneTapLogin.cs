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
    // If a user is signed in, this will end their session.
    [DllImport("__Internal")]
    private static extern void LogOutGoogleOneTap();

    // The Google OAuth client ID.
    private static readonly string TESTING_CLIENT_ID = "787231947800-ee2g4lptmfa0av2qb26n1qu60hf5j2fd.apps.googleusercontent.com";
    private static readonly string REAL_CLIENT_ID = "787231947800-ee2g4lptmfa0av2qb26n1qu60hf5j2fd.apps.googleusercontent.com";

    // This button is now disabled. Searches for it will return null.
    private static readonly string LOGOUT_BUTTON_TAG = "GOOGLE_LOGOUT";

    private Logger _logger;
    private bool _loggedIn = false;

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
        _loggedIn = false;
    }

    private bool _loginDisplayed = false;

    public bool LoggedIn()
    {
        return _loggedIn;
    }

    public bool LoginDisplayed()
    {
        return _loginDisplayed;
    }

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
        _loggedIn = true;
        // Show the logout button.
        GameObject logoutButton = GameObject.FindGameObjectWithTag(LOGOUT_BUTTON_TAG);
        if (logoutButton != null)
        {
            logoutButton.SetActive(true);
        }
        _loginDisplayed = false;
    }

    public void CancelLoginUI()
    {
        _logger.Info("CancelLoginUI() called.");
        CancelGoogleOneTap();
        _loginDisplayed = false;
    }

    public void LogOut()
    {
        _logger.Info("LogOut() called.");
        LogOutGoogleOneTap();
        _loggedIn = false;
        _loginDisplayed = false;
        // Hide the logout button.
        GameObject logoutButton = GameObject.FindGameObjectWithTag(LOGOUT_BUTTON_TAG);
        if (logoutButton != null)
        {
            logoutButton.SetActive(false);
        }
        // End the current websocket connection, since it's authenticated.
        Network.NetworkManager.TaggedInstance().RestartConnection();
        ShowLoginUI();
    }
}
