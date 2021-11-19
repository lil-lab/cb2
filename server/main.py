import aiohttp
import asyncio
import fire
import hashlib
import json
import os
import pygame
import sys
import time

from aiohttp import web
from hex import HecsCoord, HexBoundary, HexCell
from messages import map_update
from messages import message_from_server
from messages import message_to_server
from messages import state_sync
from messages.rooms import JoinResponse
from messages.rooms import Role
from messages.rooms import RoomManagementResponse
from messages.rooms import RoomResponseType
from room_manager import RoomManager
from map_tools import visualize

from datetime import datetime

routes = web.RouteTableDef()

# A table of active websocket connections. Maps from ID to info.
remote_table = {}

# Keeps track of game state.
room_manager = RoomManager()

# Used if run with GUI enabled.
SCREEN_SIZE = 1000


async def transmit(ws, message):
    global remote_table
    if ws not in remote_table:
        return ValueError("Agent ID not found in remote table")

    remote_table[ws]["bytes_down"] += len(message)
    remote_table[ws]["last_message_down"] = time.time()

    await ws.send_str(message)


@routes.get('/status')
async def Index(request):
    global assets_map
    global remote_table
    global room_manager
    server_state = {
        "assets": assets_map,
        "endpoints": remote_table,
        "number_rooms": len(room_manager.room_ids()),
        "rooms": [room_manager.get_room(room_id).state() for room_id in room_manager.rooms()]
    }
    return web.json_response(server_state)


async def stream_game_state(request, ws):
    global remote_table
    global room_manager

    client_initialized = False
    while not ws.closed:
        await asyncio.sleep(0.1)
        if not room_manager.socket_in_room(ws):
            client_initialized = False
            continue

        (room_id, player_id, role) = room_manager.socket_info(ws)
        room = room_manager.get_room(room_id)

        if not client_initialized:
            # Notify the user that they've joined a room, then send the map.
            join_notification = RoomManagementResponse(
                RoomResponseType.JOIN_RESPONSE, None, JoinResponse(True, None, role))
            room_response = message_from_server.MessageFromServer(datetime.now(
            ), message_from_server.MessageType.ROOM_MANAGEMENT, None, None, None, join_notification)
            await transmit(ws, room_response.to_json())
            mupdate = room.map()
            msg = message_from_server.MessageFromServer(
                datetime.now(), message_from_server.MessageType.MAP_UPDATE, None, mupdate, None)
            await transmit(ws, msg.to_json())
            client_initialized = True

        msg_from_server = room.drain_message(player_id)
        if msg_from_server is not None:
            await transmit(ws, msg_from_server.to_json())


async def receive_agent_updates(request, ws):
    global remote_table
    global room_manager
    async for msg in ws:
        await asyncio.sleep(0.01)
        if msg.type == aiohttp.WSMsgType.ERROR:
            closed = True
            await ws.close()
            print('ws connection closed with exception %s' % ws.exception())
            continue

        if msg.type != aiohttp.WSMsgType.TEXT:
            continue

        remote_table[ws]["last_message_up"] = time.time()
        remote_table[ws]["bytes_up"] += len(msg.data)

        if msg.data == 'close':
            closed = True
            await ws.close()
            continue

        print("Received msg: " + msg.data)
        message = message_to_server.MessageToServer.from_json(msg.data)
        # Only handle in-game actions if we're in a room.
        if room_manager.socket_in_room(ws):
            (room_id, player_id) = room_manager.socket_info(
                ws)["room_id", "player_id"]
            room = room_manager.get_room(room_id)
            if message.type == message_to_server.MessageType.ACTIONS:
                print(
                    "Action received. Transmit: {0}, Type: {1}, Actions:")
                for action in message.actions:
                    print("{0}:{1}".format(action.id, action.displacement))
                    room.handle_action(player_id, action)
                continue
            if message.type == message_to_server.MessageType.STATE_SYNC_REQUEST:
                room.desync(player_id)
                continue

        if message.type == message_to_server.MessageType.ROOM_MANAGEMENT:
            response = room_manager.handle_request(message.room_request, ws)
            if response is not None:
                msg = message_from_server.MessageFromServer(
                    datetime.now(), message_from_server.MessageType.ROOM_MANAGEMENT, None, None, None, response)
                await transmit(ws, msg.to_json())
            continue

        print("Received unknown message type:" + str(message.type))


@routes.get('/player_endpoint')
async def PlayerEndpoint(request):
    global remote_table
    global room_manager
    ws = web.WebSocketResponse(autoclose=True, heartbeat=1.0, autoping=1.0)
    await ws.prepare(request)
    print("player connected from : " + request.remote)
    remote_table[ws] = {"last_message_up": time.time(), "last_message_down": time.time(
    ), "ip": request.remote, "id": 0, "bytes_up": 0, "bytes_down": 0}
    try:
        await asyncio.gather(receive_agent_updates(request, ws), stream_game_state(request, ws))
    finally:
        print("player disconnected from : " + request.remote)
        await room_manager.disconnect_socket(ws)
        del remote_table[ws]
    return ws


def HashCollectAssets(assets_directory):
    assets_map = {}
    for item in os.listdir(assets_directory):
        assets_map[hashlib.md5(item.encode()).hexdigest()
                   ] = os.path.join(assets_directory, item)
    return assets_map


# A dictionary from md5sum to asset filename.
assets_map = {}

# Serves assets obfuscated by md5suming the filename.
# This is used to prevent asset discovery.


@routes.get('/assets/{asset_id}')
async def asset(request):
    asset_id = request.match_info.get('asset_id', "")
    if (asset_id not in assets_map):
        raise aiohttp.web.HTTPNotFound('/redirect')
    return web.FileResponse(assets_map[asset_id])


async def serve():
    app = web.Application()

    # Add a route for serving web frontend files on /.
    routes.static('/', './www/')

    app.add_routes(routes)
    runner = runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, None, 8080)
    await site.start()

    print("======= Serving on {site.name} ======".format(site=site))

    # pause here for very long time by serving HTTP requests and
    # waiting for keyboard interruption
    while True:
        await asyncio.sleep(1)


async def debug_print():
    global room_manager
    room = room_manager.get_room_by_name("debug")
    while True:
        await asyncio.sleep(5)
        if room is None:
            room = room_manager.get_room_by_name("debug")
            continue

        state = room.state()
        print(state)


async def draw_gui():
    global room_manager
    room = room_manager.get_room_by_name("debug")
    display = visualize.GameDisplay(SCREEN_SIZE)
    while True:
        await asyncio.sleep(0.05)
        if room is None:
            room = room_manager.get_room_by_name("debug")
            continue
        state = room.state()
        map = room.map()
        display.set_map(map)
        display.set_game_state(state)
        display.draw()
        pygame.display.flip()
        event = pygame.event.wait(10)
        if event.type == pygame.QUIT:
            pygame.quit()
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.quit()
                return


def main(assets_directory="assets/", gui=False):
    global assets_map
    global room_manager
    assets_map = HashCollectAssets(assets_directory)
    tasks = asyncio.gather(room_manager.matchmake(),
                           draw_gui(), debug_print(), serve())
    # If map visualization command line flag is enabled, run with the visualize task.
    # if gui:
    #   tasks = asyncio.gather(tasks, draw_gui())
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(tasks)
    except KeyboardInterrupt:
        pass
    finally:
        room_manager.end_server()
        loop.close()


if __name__ == "__main__":
    fire.Fire(main)
