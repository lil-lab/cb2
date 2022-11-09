using System;

namespace Network
{
    [Serializable]
    public class GoogleAuth
    {
        // OAuth2 token.
        public string token;
    }

    [Serializable]
    public class GoogleAuthConfirmation
    {
        // True if the token was valid.
        public bool auth_success;
        // Rest is only populated if auth_success.
        public int user_id;
        public string user_name;
    }

}