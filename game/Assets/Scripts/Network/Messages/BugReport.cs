using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class BugReport
    {
        public MapUpdate MapUpdate;
        public List<TurnState> TurnStateLog;
        public StateSync StateSync;
    }
}