// Extension of BugReport for uploading exceptions from the client.
using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class ClientException
    {
        public BugReport bug_report;
        public string condition;
        public string stack_trace;
        public string game_id;
        public string role;
    }
}