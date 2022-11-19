using System;
using System.Collections.Generic;

namespace Network
{

    [Serializable]
    public class MessageToServer
    {
        public enum MessageType
        {
            // Send list of player actions to the server.
            ACTIONS = 0,
            // Request the server send a state synch.
            STATE_SYNC_REQUEST,

            // Used to join a new game/other game management actions.
            ROOM_MANAGEMENT,
            // Used by the leader to send objectives (tasks) to the follower.
            OBJECTIVE,
            // Used by the follower to signal that an objective has been completed.
            OBJECTIVE_COMPLETE,
            TURN_COMPLETE,
            TUTORIAL_REQUEST,
            PONG,
            LIVE_FEEDBACK,
            CANCEL_PENDING_OBJECTIVES,
            GOOGLE_AUTH,
            USER_INFO,
        }

        // These fields are populated for every packet.
        public string transmit_time;  // Transmission time of this message in ISO 8601 format.

        // Depending on the type, One of the following may be populated.
        public MessageType type;

        public List<Action> actions;
        public RoomManagementRequest room_request;
        public ObjectiveMessage objective;
        public ObjectiveCompleteMessage objective_complete;
        public TurnComplete turn_complete;
        public TutorialRequest tutorial_request;
        public Pong pong;
        public LiveFeedback live_feedback;
        public GoogleAuth google_auth;
    }

}  // namespace Network
