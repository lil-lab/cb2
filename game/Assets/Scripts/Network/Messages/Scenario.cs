using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class Scenario
    {
        public MapUpdate map;
        public PropUpdate prop;
        public TurnState turn;
        public List<ObjectiveMessage> objectives;
        public StateSync actor_state;
    }

    public enum ScenarioRequestType
    {
        NONE = 0,
    }

    [Serializable]
    public class ScenarioRequest
    {
        public ScenarioRequestType type;
    }

    public enum ScenarioResponseType
    {
        NONE = 0,
        LOADED = 1,
        TRIGGER_REPORT = 2,
        SCENARIO_DOWNLOAD = 3,
    }

    [Serializable]
    public class ScenarioResponse
    {
        public ScenarioResponseType type;
    }

}