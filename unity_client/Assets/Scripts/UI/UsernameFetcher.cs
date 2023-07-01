using System;
using System.Collections;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

public class UsernameFetcher : MonoBehaviour
{

    [Serializable]
    class UsernameRecord
    {
        public string username;
    }

    private UsernameRecord _record = null;
    private bool _usernameDisplayed = false;

    // Start is called before the first frame update
    void Start()
    {
        Dictionary<string, string> urlParams = Network.NetworkManager.UrlParameters();
        if (urlParams.ContainsKey("workerId"))
        {
            StringBuilder sb = new StringBuilder();
            using (MD5 md5 = MD5.Create())
            {
                byte[] hash = md5.ComputeHash(new UTF8Encoding().GetBytes(urlParams["workerId"]));
    
                foreach (byte b in hash)
                    sb.Append(b.ToString("X2"));
            }
            StartCoroutine(GetUsername(sb.ToString()));
        } else {
            Debug.Log("No workerId found in URL");
            return;
        }
    }

    // Update is called once per frame
    void Update()
    {
        if (_record != null && !_usernameDisplayed)
        {
            GetComponent<TMPro.TMP_Text>().text = "Username: " + _record.username;
            _usernameDisplayed = true;
        }
    }


    IEnumerator GetUsername(string md5hash)
    {
        string base_url = Network.NetworkManager.BaseUrl(/*websocket=*/false);
        using (UnityWebRequest webRequest = UnityWebRequest.Get(base_url + "data/username_from_hash/" + md5hash))
        {
            // Request and wait for the desired page.
            yield return webRequest.SendWebRequest();

            switch (webRequest.result)
            {
                case UnityWebRequest.Result.ConnectionError:
                case UnityWebRequest.Result.DataProcessingError:
                    Debug.LogError("Error: " + webRequest.error);
                    break;
                case UnityWebRequest.Result.ProtocolError:
                    Debug.LogError("HTTP Error: " + webRequest.error);
                    break;
                case UnityWebRequest.Result.Success:
                    Debug.Log("Received: " + webRequest.downloadHandler.text);
                    _record = JsonUtility.FromJson<UsernameRecord>(webRequest.downloadHandler.text);
                    break;
            }
        }
    }
}
