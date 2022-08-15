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
    }
}  // namespace Network
