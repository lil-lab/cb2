import aiohttp
import asyncio
import fire
import hashlib
import json
import logging
import os
import pathlib
import pygame
import sys
import time

from aiohttp import web
from dataclasses import astuple
from hex import HecsCoord, HexBoundary, HexCell
from messages import map_update
from messages import message_from_server
from messages import message_to_server
from messages import state_sync
from messages.rooms import JoinResponse
from messages.rooms import Role
from messages.rooms import RoomManagementResponse
from messages.rooms import RoomResponseType
from remote_table import Remote, AddRemote, GetRemote, DeleteRemote, GetRemoteTable
from room_manager import RoomManager
from map_tools import visualize

from datetime import datetime

routes = web.RouteTableDef()

# Keeps track of game state.
room_manager = RoomManager()

# Used if run with GUI enabled.
SCREEN_SIZE = 1000

logger = logging.getLogger()

async def transmit(ws, message):
    remote = GetRemote(ws)
    if remote is None:
        return ValueError("Agent ID not found in remote table")

    remote.bytes_down += len(message)
    remote.last_message_down = time.time()

    await ws.send_str(message)


@routes.get('/status')
async def Index(request):
    global assets_map
    global room_manager
    remote_table = GetRemoteTable()
    player_queue = {str(x):remote_table[x] for x in room_manager.player_queue()}

    server_state = {
        "assets": assets_map,
        "number_rooms": len(room_manager.room_ids()),
        "remotes": [remote_table[ws] for ws in remote_table],
        "room_manager_remotes":[str(room_manager.socket_info(ws)) for ws in remote_table],
        "rooms": [room_manager.get_room(room_id).state().to_json() for room_id in room_manager.room_ids()],
        "player_queue": player_queue,
        "room_debug_info": [room_manager.get_room(room_id).debug_status() for room_id in room_manager.room_ids()],
    }
    pretty_dumper = lambda x: json.dumps(x, indent=4, sort_keys=True)
    return web.json_response(server_state, dumps=pretty_dumper)


async def stream_game_state(request, ws):
    global room_manager

    client_initialized = False
    while not ws.closed:
        if not room_manager.socket_in_room(ws):
            await asyncio.sleep(0.001)
            client_initialized = False
            continue

        (room_id, player_id, role) = astuple(room_manager.socket_info(ws))
        room = room_manager.get_room(room_id)

        if room is None:
            logger.warn("room_manager.socket_in_room() returned true but room lookup failed.")
            await asyncio.sleep(0.001)
            client_initialized = False
            continue

        if not client_initialized:
            # Notify the user that they've joined a room.
            join_notification = RoomManagementResponse(
                RoomResponseType.JOIN_RESPONSE, None, JoinResponse(True, 0, role), None)
            room_response = message_from_server.RoomResponseFromServer(
                join_notification)
            await transmit(ws, room_response.to_json())
            # Sleep to give the client some time to change scenes.
            await asyncio.sleep(1.0)
            client_initialized = True
            continue

        msg_from_server = room.drain_message(player_id)
        if msg_from_server is not None:
            await transmit(ws, msg_from_server.to_json())
        await asyncio.sleep(0.001)


async def receive_agent_updates(request, ws):
    global room_manager
    async for msg in ws:
        await asyncio.sleep(0.001)
        if ws.closed:
            return
        if msg.type == aiohttp.WSMsgType.ERROR:
            closed = True
            await ws.close()
            print('ws connection closed with exception %s' % ws.exception())
            continue

        if msg.type != aiohttp.WSMsgType.TEXT:
            continue

        remote = GetRemote(ws)
        remote.last_message_up = time.time()
        remote.bytes_up += len(msg.data)

        if msg.data == 'close':
            closed = True
            await ws.close()
            continue

        logger.debug("Raw message: " + msg.data)
        message = message_to_server.MessageToServer.from_json(msg.data)

        if message.type == message_to_server.MessageType.ROOM_MANAGEMENT:
            response = await room_manager.handle_request(message.room_request, ws)
            if response is not None:
                msg = message_from_server.RoomResponseFromServer(response)
                await transmit(ws, msg.to_json())
            continue

        # Only handle in-game actions if we're in a room.
        if room_manager.socket_in_room(ws):
            (room_id, player_id, _) = astuple(room_manager.socket_info(
                ws))
            room = room_manager.get_room(room_id)
            room.handle_packet(player_id, message)


@routes.get('/player_endpoint')
async def PlayerEndpoint(request):
    global room_manager
    ws = web.WebSocketResponse(autoclose=True, heartbeat=10.0, autoping=1.0)
    await ws.prepare(request)
    logger = logging.getLogger()
    logger.info("player connected from : " + request.remote)
    AddRemote(ws, Remote(request.remote, 0, 0, time.time(), time.time(), request, ws))
    try:
        await asyncio.gather(receive_agent_updates(request, ws), stream_game_state(request, ws))
    finally:
        logger.info("player disconnected from : " + request.remote)
        await room_manager.disconnect_socket(ws)
        DeleteRemote(ws)
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
    loop = asyncio.get_event_loop()
    prev_tasks = set(asyncio.all_tasks())
    while True:
        await asyncio.sleep(0.001)
        tasks = set(asyncio.all_tasks())
        if len(prev_tasks) != len(tasks):
            logger.debug(
                f"New task added. size: {len(tasks)}. prev size: {len(prev_tasks)}.")
            logger.debug(
                "========================= New Tasks added =========================")
            logger.debug(f"{str(tasks - prev_tasks)}")
            logger.debug(
                "========================= New Tasks removed =========================")
            logger.debug(f"{str(prev_tasks - tasks)}")
        prev_tasks = tasks
        if room is None:
            room = room_manager.get_room_by_name("Room 0")
            continue
        state = room.state()
        print(state)


async def draw_gui():
    global room_manager
    room = room_manager.get_room_by_name("Room #0")
    display = visualize.GameDisplay(SCREEN_SIZE)
    while True:
        await asyncio.sleep(0.001)
        if room is None:
            room = room_manager.get_room_by_name("Room #0")
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


def InitServerLogging():
    """  Server logging intended for debugging a server crash.
    
    The server log includes the following, interlaced:
    - Events from each game room.
    - HTTP connection, error & debug information from aiohttp.
    - Misc other server logs (calls to logger.info()).
    - Exception stack traces."""
    log_format = "[%(asctime)s] %(name)s %(levelname)s [%(module)s:%(funcName)s:%(lineno)d] %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)
    logging.getLogger("asyncio").setLevel(logging.INFO)


def InitGameLogging(log_directory):
    """ Game logging allows us to record and later playback individual games.

    Each game is given a game id. Logs for a single game are stored in a
    directory with a name of the form: 

    log_directory/<datetime>_<game_id>/...

    where <datetime> is in iso8601 format."""
    log_base_dir = pathlib.Path(log_directory)

    # Create the directory if it doesn't exist.
    log_base_dir.mkdir(parents=False, exist_ok=True)

    # Register the logging directory with the room manager.
    room_manager.register_game_logging_directory(log_base_dir)


def main(log_directory="logs/", assets_directory="assets/", gui=False):
    global assets_map
    global room_manager

    # Initialize server & game logging.
    InitServerLogging()
    InitGameLogging(log_directory)

    assets_map = HashCollectAssets(assets_directory)
    tasks = asyncio.gather(room_manager.matchmake(), room_manager.cleanup_rooms(), debug_print(), serve())
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
