from datetime import datetime

import server.messages as messages
import server.messages.message_to_server as message_to_server
from server.messages import live_feedback, turn_state
from server.messages.objective import ObjectiveCompleteMessage, ObjectiveMessage
from server.messages.rooms import Role, RoomManagementRequest, RoomRequestType


def EndTurnMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.TURN_COMPLETE,
        turn_complete=turn_state.TurnComplete(),
    )
    return message


def LeaveMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.ROOM_MANAGEMENT,
        room_request=RoomManagementRequest(type=RoomRequestType.LEAVE),
    )
    return message


def InstructionMessage(instruction_text):
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.OBJECTIVE,
        objective=ObjectiveMessage(Role.LEADER, instruction_text),
    )
    return message


def PositiveFeedbackMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.LIVE_FEEDBACK,
        live_feedback=message_to_server.LiveFeedback(
            live_feedback.FeedbackType.POSITIVE
        ),
    )
    return message


def PongMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.PONG,
        pong=message_to_server.Pong(datetime.utcnow()),
    )
    return message


def NegativeFeedbackMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.LIVE_FEEDBACK,
        live_feedback=message_to_server.LiveFeedback(
            live_feedback.FeedbackType.NEGATIVE
        ),
    )
    return message


def InterruptMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(), type=message_to_server.MessageType.INTERRUPT
    )
    return message


def JoinQueueMessage(i_uuid: str = ""):
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.ROOM_MANAGEMENT,
        room_request=message_to_server.RoomManagementRequest(
            messages.rooms.RoomRequestType.JOIN, i_uuid
        ),
    )
    return message


def InstructionDoneMessage(uuid):
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.OBJECTIVE_COMPLETED,
        objective_complete=ObjectiveCompleteMessage(uuid),
    )
    return message


def JoinFollowerQueueMessage(i_uuid: str = ""):
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.ROOM_MANAGEMENT,
        room_request=message_to_server.RoomManagementRequest(
            messages.rooms.RoomRequestType.JOIN_FOLLOWER_ONLY, i_uuid
        ),
    )
    return message


def JoinLeaderQueueMessage(i_uuid: str = ""):
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.ROOM_MANAGEMENT,
        room_request=message_to_server.RoomManagementRequest(
            messages.rooms.RoomRequestType.JOIN_LEADER_ONLY, i_uuid
        ),
    )
    return message


def ActionsMessage(actions):
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.ACTIONS,
        actions=actions,
    )
    return message
