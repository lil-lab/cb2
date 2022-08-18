import server.messages.action as action
import server.messages as messages
import server.messages.message_from_server as message_from_server
import server.messages.message_to_server as message_to_server

from datetime import datetime
from datetime import timedelta

from server.hex import HecsCoord
from server.messages import turn_state
from ..server.messages.objective import ObjectiveCompleteMessage

def EndTurnMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.now(),
        type=message_to_server.MessageType.TURN_COMPLETE,
        turn_complete=turn_state.TurnComplete())
    return message

def InstructionMessage(instruction_text):
    message = message_to_server.MessageToServer(
        transmit_time=datetime.now(),
        type=message_to_server.MessageType.INSTRUCTION,
        instruction=message_to_server.Instruction(instruction_text))
    return message

def PositiveFeedbackMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.now(),
        type=message_to_server.MessageType.FEEDBACK,
        feedback=message_to_server.Feedback(message_to_server.FeedbackType.POSITIVE))
    return message

def PongMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.now(),
        type=message_to_server.MessageType.PONG,
        pong=message_to_server.Pong(datetime.now()))
    return message

def NegativeFeedbackMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.now(),
        type=message_to_server.MessageType.FEEDBACK,
        feedback=message_to_server.Feedback(message_to_server.FeedbackType.NEGATIVE))
    return message

def InterruptMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.now(),
        type=message_to_server.MessageType.INTERRUPT)
    return message

def JoinQueueMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.ROOM_MANAGEMENT,
        room_request=message_to_server.RoomManagementRequest(messages.rooms.RoomRequestType.JOIN))
    return message

def InstructionDoneMessage(uuid):
    message = message_to_server.MessageToServer(
        transmit_time=datetime.now(),
        type=message_to_server.MessageType.OBJECTIVE_COMPLETED,
        objective_complete=ObjectiveCompleteMessage(uuid))
    return message

def JoinFollowerQueueMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.ROOM_MANAGEMENT,
        room_request=message_to_server.RoomManagementRequest(messages.rooms.RoomRequestType.JOIN_FOLLOWER_ONLY))
    return message

def JoinLeaderQueueMessage():
    message = message_to_server.MessageToServer(
        transmit_time=datetime.utcnow(),
        type=message_to_server.MessageType.ROOM_MANAGEMENT,
        room_request=message_to_server.RoomManagementRequest(messages.rooms.RoomRequestType.JOIN_LEADER_ONLY))
    return message

def RotateAction(player_id, rotation_degrees):
    message = message_to_server.MessageToServer(
        transmit_time=datetime.now(),
        type=message_to_server.MessageType.ACTIONS,
        actions=[
            action.Action(player_id,
            action.ActionType.ROTATE,
            action.AnimationType.ROTATE,
            HecsCoord(0, 0, 0),
            rotation_degrees,
            0,
            action.Color(0, 0, 0, 0),
            0.1,
            datetime.now() + timedelta(seconds=15))])
    return message