using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class Scenario
    {
        public MapUpdate map;
        public PropUpdate prop_update;
        public TurnState turn_state;
        public List<ObjectiveMessage> objectives;
        public StateSync actor_state;
    }

    public enum ScenarioRequestType
    {
        NONE = 0,
        LOAD_SCENARIO = 1,
        END_SCENARIO = 2,
        REGISTER_TRIGGER = 3,
        UNREGISTER_TRIGGER = 4,
    }

    [Serializable]
    public class ScenarioRequest
    {
        public ScenarioRequestType type;
        public string scenario_data = null;
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
        public string scenario_download;
    }
}