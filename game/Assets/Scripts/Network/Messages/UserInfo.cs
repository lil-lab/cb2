using System;

namespace Network
{
    public enum UserType
    {
        NONE = 0,
        MTURK,
        OPEN,
        GOOGLE,
        BOT
    }

    [Serializable]
    public class UserInfo
    {
        public string user_name;
        public UserType user_type;
    }
}