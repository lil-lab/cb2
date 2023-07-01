using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class ModuleLog
    {
        public string module;
        public string log;
    }

    [Serializable]
    public class BugReport
    {
        public MapUpdate map_update;
        public List<TurnState> turn_state_log;
        public StateSync state_sync;
        public List<ModuleLog> logs;
    }
}