using System;
using System.Collections.Generic;

namespace Network
{
    [Serializable]
    public class MessageFromServer
    {
        public enum MessageType
        {
            ACTIONS = 0,
            MAP_UPDATE,
            STATE_SYNC,
            ROOM_MANAGEMENT,
            OBJECTIVE,
            TURN_STATE,
            TUTORIAL_RESPONSE,
            PING,
            LIVE_FEEDBACK,
            PROP_UPDATE,
            STATE_MACHINE_TICK,
            GOOGLE_AUTH_CONFIRMATION,
            USER_INFO,
            PROP_SPAWN,
            PROP_DESPAWN,
            REPLAY_RESPONSE,
            SCENARIO_RESPONSE,
            MENU_OPTIONS,
            SOUND_TRIGGER,
        }

        // These fields are always provided with any packet.
        public string transmit_time;  // When the server transmitted this message in ISO 8601 format.

        // Message Type.
        public MessageType type;

        // Only one of these is populated. Check the message type.
        public List<Action> actions;
        public MapUpdate map_update;
        public StateSync state;
        public RoomManagementResponse room_management_response;
        public List<ObjectiveMessage> objectives;
        public TurnState turn_state;
        public TutorialResponse tutorial_response;
        public LiveFeedback live_feedback;
        public PropUpdate prop_update;
        public StateMachineInfo state_machine_tick;
        public GoogleAuthConfirmation google_auth_confirmation;
        public UserInfo user_info;
        public Prop prop_spawn;
        public List<Prop> prop_despawn;
        public ReplayResponse replay_response;
        public ScenarioResponse scenario_response;
        public MenuOptions menu_options;
        public SoundTrigger sound_trigger;
    }
}  // namespace Network