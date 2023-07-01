using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class Scenario
    {
        public string scenario_id; // Unique identifier for the scenario. Used to attach to a scenario.
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
        ATTACH_TO_SCENARIO = 5,
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
        SCENARIO_DOWNLOAD = 3,
    }

    [Serializable]
    public class ScenarioResponse
    {
        public ScenarioResponseType type;
        public string scenario_download;
    }
}