using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class ModuleLog
    {
        public string Module;
        public string Log;
    }

    [Serializable]
    public class BugReport
    {
        public MapUpdate MapUpdate;
        public List<TurnState> TurnStateLog;
        public StateSync StateSync;
        public List<ModuleLog> Logs;
    }
}