import aiohttp
import asyncio
import fire
import orjson
import statistics as stats

from datetime import datetime
from datetime import timedelta

from server.messages import message_from_server
from server.messages import message_to_server
from server.messages import action
from server.messages import turn_state
from server.messages.objective import ObjectiveMessage
import server.messages.rooms

from server.hex import HecsCoord

# Connect via websocket to the server's /player_endpoint endpoint.
async def connect_to_server(server_url):
    url = f"{server_url}/player_endpoint"
    print(f"Connecting to {url}...")
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(url)
    print(f"Connected!")
    return session, ws

async def join_room(ws):
    message = JoinRoomToServer()
    binary_message = orjson.dumps(message, option=orjson.OPT_NAIVE_UTC)
    await ws.send_str(binary_message.decode('utf-8'))

async def wait_for_join_messages(ws):
    player_role = None
    player_id = None
    while True:
        message = await ws.receive()
        if message is None:
            continue
        if message.type == aiohttp.WSMsgType.ERROR:
            print(f"Received error: {message.data}")
            continue
        if message.type != aiohttp.WSMsgType.TEXT:
            print(f"wait_for_join_messages received unexpected message type: {message.type}. data: {message.data}")
            continue
        response = message_from_server.MessageFromServer.from_json(message.data)
        if response.type == message_from_server.MessageType.ROOM_MANAGEMENT:
            if response.room_management_response.type == server.messages.rooms.RoomResponseType.JOIN_RESPONSE:
                join_message = response.room_management_response.join_response
                if join_message.joined == True:
                    print(f"Joined room. Role: {join_message.role}")
                    player_role = join_message.role
                else:
                    print(f"Place in queue: {join_message.place_in_queue}")
        if response.type == message_from_server.MessageType.STATE_SYNC:
            print(f"Received state sync. Player id: {response.state.player_id}")
            player_id = response.state.player_id
        if player_role != None and player_id != None:
            return player_role, player_id

async def send_turn_action(ws, player_id, rotation_degrees):
    if ws.closed:
        return
    try:
        message = TurnAction(player_id, rotation_degrees)
        print(f"Sending message: {message}")
        await ws.send_str(message.to_json())
        transmit_times[rotation_degrees] = datetime.now()
        if rotation_degrees not in receive_times:
            receive_times[rotation_degrees] = []
    except:
        return

def TurnAction(player_id, rotation_degrees):
    message = message_to_server.MessageToServer(transmit_time=datetime.now(), type=message_to_server.MessageType.ACTIONS, actions=[action.Action(player_id, action.ActionType.ROTATE, action.AnimationType.ROTATE, HecsCoord(0, 0, 0), rotation_degrees, 0, action.Color(0, 0, 0, 0), 0.1, datetime.now() + timedelta(seconds=15))])
    return message

def JoinRoomToServer():
    message = message_to_server.MessageToServer(transmit_time=datetime.utcnow(),
    type=message_to_server.MessageType.ROOM_MANAGEMENT, actions=None,
    room_request=message_to_server.RoomManagementRequest(server.messages.rooms.RoomRequestType.JOIN))
    print(f"Sending message: {message}")
    return message

async def wait_for_turn(ws, player_id, role, receive_times):
    while True:
        if ws.closed:
            return
        try:
            message = await ws.receive()
        except:
            return
        if message is None:
            continue
        if message.type == aiohttp.WSMsgType.ERROR:
            print(f"Received error: {message.data}")
            continue
        if message.type == aiohttp.WSMsgType.CLOSE:
            print(f"wait_for_turn received end message.")
            return
        if message.type == aiohttp.WSMsgType.PING:
            print(f"wait_for_turn received PING message.")
            return
        if message.type == aiohttp.WSMsgType.PONG:
            print(f"wait_for_turn received PONG message.")
            return
        if message.type == aiohttp.WSMsgType.BINARY:
            print(f"wait_for_turn received BINARY message.")
            return
        if message.type != aiohttp.WSMsgType.TEXT:
            print(f"wait_for_turn received unexpected message type: {message.type}. data: {message.data}")
            continue
        response = message_from_server.MessageFromServer.from_json(message.data)
        if response.type == message_from_server.MessageType.ACTIONS:
            for action in response.actions:
                message_id = action.rotation
                if message_id in receive_times:
                    receive_times[message_id].append(datetime.now())
        if response.type == message_from_server.MessageType.GAME_STATE:
            print(f"Game state received. turn end: {response.turn_state.turn_end}. current turn: {response.turn_state.turn}")
            game_state = response.turn_state
            if game_state.turn == role:
                return
            else:
                await asyncio.sleep(0.1)

from enum import Enum
class State(Enum):
    NONE = 0
    START = 1
    JOIN_SENT = 2
    JOINED = 3
    WAITING_FOR_TURN = 4
    TURN = 5
    DONE = 6


ws_state = {}
player_role = {}
player_id = {}
transmit_times = {}
receive_times = {}
message_no = 0
last_monitor_update = datetime.now()
all_joined = False

async def monitor_task():
    global last_monitor_update
    global all_joined
    global ws_state
    while True:
        await asyncio.sleep(0.1)
        if datetime.now() - last_monitor_update > timedelta(seconds=3):
            print(f"Monitoring task: {ws_state}")
            last_monitor_update = datetime.now()
        if (len(ws_state.values()) > 0) and all([x == State.JOINED for x in ws_state.values()]) and (not all_joined):
            print(f"All joined")
            all_joined = True
        if len(ws_state.values()) > 0 and all([x == State.DONE for x in ws_state.values()]):
            print("All done")
            break

async def handle_receive(ws):
    global all_joined
    global receive_times
    while ws_state[ws] != State.JOIN_SENT:
        await asyncio.sleep(0.1)
    result = await wait_for_join_messages(ws)
    if (result == None):
      return
    player_role[ws], player_id[ws] = result
    print(f"Player JOINED.")
    print(f"Player role: {player_role[ws]}")
    print(f"Player id: {player_id[ws]}")
    ws_state[ws] = State.JOINED
    while not all_joined:
        await asyncio.sleep(0.1)
    while True:
        await asyncio.sleep(0.1)
        if ws.closed:
            ws_state[ws] = State.DONE
            return
        if (ws_state[ws] == State.WAITING_FOR_TURN):
            print(f"Waiting for turn.")
            await wait_for_turn(ws, player_id[ws], player_role[ws], receive_times)
            ws_state[ws] = State.TURN
        if (ws_state[ws] == State.DONE):
            ws.close()
            return

async def send_instruction(ws, message_string):
    if ws.closed:
        return
    try:
        message = message_to_server.MessageToServer(transmit_time=datetime.now(),
          type=message_to_server.MessageType.OBJECTIVE,
          objective=ObjectiveMessage(server.messages.rooms.Role.LEADER, message_string))
        print(f"Sending message: {message}")
        await ws.send_str(message.to_json())
    except:
        return


async def handle_send(ws, messages_per_socket):
    global message_no
    global all_joined
    await join_room(ws)
    ws_state[ws] = State.JOIN_SENT
    while ws_state[ws] != State.JOINED:
        await asyncio.sleep(0.1)
    while not all_joined:
        await asyncio.sleep(0.1)
    messages_sent = 0
    while True:
        await asyncio.sleep(0.1)
        if ws.closed:
            ws_state[ws] = State.DONE
            return
        if messages_sent >= messages_per_socket:
            print(f"=========== Sent {messages_sent} messages!")
            ws_state[ws] = State.DONE
            await ws.close()
            return
        if (ws_state[ws] == State.TURN) or (ws_state[ws] == State.JOINED):
            messages_to_send = 5 if player_role[ws] == server.messages.rooms.Role.LEADER else 15
            messages_to_send = min(messages_to_send, messages_per_socket - messages_sent)
            for i in range(messages_to_send):
                await send_turn_action(ws, player_id[ws], message_no)
                messages_sent += 1
                message_no += 0.01
            if player_role[ws] == server.messages.rooms.Role.LEADER:
                await send_instruction(ws, "Automated test player, please leave game.")
            await end_turn(ws)
            ws_state[ws] = State.WAITING_FOR_TURN

def EndTurnToServer():
    message = message_to_server.MessageToServer(transmit_time=datetime.now(), type=message_to_server.MessageType.TURN_COMPLETE, turn_complete=turn_state.TurnComplete())
    print(f"Sending message: {message}")
    return message

async def end_turn(ws):
    try:
        if ws.closed:
            return
        message = EndTurnToServer()
        await ws.send_str(message.to_json())
    except:
        return

async def main(server_url="ws://localhost:8080", num_sockets=20, messages_per_socket=100, verbose=False):
    # Connect to the server.
    sessions = []
    wss = []
    for i in range(num_sockets):
        session, ws = await connect_to_server(server_url)
        sessions.append(session)
        wss.append(ws)
    
    tasks = []
    for ws in wss:
        ws_state[ws] = State.START
        receive_task = handle_receive(ws)
        tasks.append(receive_task)
        send_task = handle_send(ws, messages_per_socket)
        tasks.append(send_task)
    
    tasks.append(monitor_task())

    await asyncio.gather(*tasks)

    global receive_times
    global transmit_times

    total_rtts = []
    for message_no in transmit_times:
        if message_no in receive_times:
            start_time = transmit_times[message_no]
            received = receive_times[message_no]
            rtts = [(rt - start_time).total_seconds() for rt in received]
            if len(rtts) > 0:
                total_rtts.extend(rtts)
    # Print min, max, mean and median RTTs:
    print(f"Min RTT: {min(total_rtts)}")
    print(f"Max RTT: {max(total_rtts)}")
    print(f"Mean RTT: {stats.mean(total_rtts)}")
    print(f"Median RTT: {stats.median(total_rtts)}")


    print("Disconnecting from server.")

    for session in sessions:
        await session.close()

if __name__ == "__main__":
    fire.Fire(main)
