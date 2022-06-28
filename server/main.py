from ast import Global
from threading import local
import aiohttp
import asyncio
import fire
import hashlib
import io
import itertools
import json
import orjson
import logging
import os
import pathlib
import peewee
import pygame
import shutil
import sys
import statistics
import tempfile
import time
import zipfile
import yappi

import schemas.defaults
import schemas.clients
import schemas.mturk
import leaderboard

import db_tools.db_utils as db_utils

from aiohttp import web
from config.config import Config, InitGlobalConfig, GlobalConfig
from dataclasses import astuple
from dateutil import parser
from dateutil import tz

from hex import HecsCoord, HexBoundary, HexCell
from map_provider import MapGenerationTask, MapPoolSize
from map_tools import visualize
from messages import map_update
from messages import message_from_server
from messages import message_to_server
from messages import state_sync
from messages.rooms import JoinResponse
from messages.rooms import Role
from messages.rooms import RoomManagementResponse
from messages.rooms import RoomResponseType
from messages.logs import GameLog, GameInfo, LogEntry
from playhouse.sqlite_ext import CSqliteExtDatabase
from remote_table import Remote, AddRemote, GetRemote, DeleteRemote, GetRemoteTable, LogConnectionEvent
from room_manager import RoomManager
from schemas import base
from db_tools import backup

from datetime import datetime, timezone, timedelta

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

    try:
        await ws.send_str(message)
    except ConnectionResetError:
        pass

async def transmit_bytes(ws, message):
    remote = GetRemote(ws)
    if remote is None:
        return ValueError("Agent ID not found in remote table")

    remote.bytes_down += len(message)
    remote.last_message_down = time.time()

    try:
        await ws.send_str(message.decode('utf-8'))
    except ConnectionResetError:
        pass

@routes.get('/')
async def Index(request):
    return web.FileResponse("www/WebGL/index.html")

@routes.get('/qualification')
async def QualificationPage(request):
    return web.FileResponse("www/qualification.html")

@routes.get('/rules')
async def Rules(request):
    return web.FileResponse("www/rules.html")

@routes.get('/example_sets')
async def Rules(request):
    return web.FileResponse("www/example_sets.html")

@routes.get('/oneoff')
async def OneoffComp(request):
    return web.FileResponse("www/oneoff.html")

@routes.get('/mturk-task')
async def TaskPage(request):
    return web.FileResponse("www/mturk-task.html")

@routes.get('/changelist')
async def Changelist(request):
    return web.FileResponse("www/changelist.html")

@routes.get('/images/{filename}')
async def Images(request):
    if not request.match_info.get('filename'):
        return web.HTTPNotFound()
    return web.FileResponse(f"www/images/{request.match_info['filename']}")

@routes.get('/status')
async def Status(request):
    global assets_map
    global room_manager
    remote_table = GetRemoteTable()
    player_queue = {str(x):str(remote_table[x]) for x in room_manager.player_queue()}

    server_state = {
        "assets": assets_map,
        "number_rooms": len(room_manager.room_ids()),
        "map_cache_size": MapPoolSize(),
        "remotes": [str(remote_table[ws]) for ws in remote_table],
        "room_manager_remotes":[str(room_manager.socket_info(ws)) for ws in remote_table],
        "rooms": [room_manager.get_room(room_id).state() for room_id in room_manager.room_ids()],
        "room_selected_cards": [str(room_manager.get_room(room_id).selected_cards()) for room_id in room_manager.room_ids()],
        "player_queue": player_queue,
        "room_debug_info": [room_manager.get_room(room_id).debug_status() for room_id in room_manager.room_ids()],
    }
    pretty_dumper = lambda x: orjson.dumps(x, option=orjson.OPT_NAIVE_UTC | orjson.OPT_INDENT_2).decode('utf-8')
    return web.json_response(server_state, dumps=pretty_dumper)

def FindGameDirectory(game_id):
    record_base_dir = pathlib.Path(GlobalConfig().record_directory())
    games = os.listdir(record_base_dir)
    for game in games:
        id = game.split("_")[1]
        if game_id == id:
            return record_base_dir / game
    return None


@routes.get('/data/messages_from_server/{game_id}')
async def MessagesFromServer(request):
    if not request.match_info.get('game_id'):
        return web.HTTPNotFound()
    game_dir = FindGameDirectory(request.match_info['game_id'])
    if not game_dir:
        return web.HTTPNotFound()
    return web.FileResponse(game_dir / "messages_from_server.json")

@routes.get('/data/messages_to_server/{game_id}')
async def MessagesToServer(request):
    if not request.match_info.get('game_id'):
        return web.HTTPNotFound()
    game_dir = FindGameDirectory(request.match_info['game_id'])
    if not game_dir:
        return web.HTTPNotFound()
    return web.FileResponse(game_dir / "messages_to_server.json")

@routes.get('/data/game_logs/{game_id}')
async def GameLogs(request):
    if not request.match_info.get('game_id'):
        return web.HTTPNotFound()
    game_dir = FindGameDirectory(request.match_info['game_id'])
    if not game_dir:
        return web.HTTPNotFound()
    game_log = GameLog(GameInfo(datetime.min, 0, "", [], []), [])
    with open(game_dir / "messages_from_server.jsonl.log", "r") as f:
        for line in f:
            log_entry_obj = orjson.loads(line)
            game_log.log_entries.append(LogEntry.from_dict(log_entry_obj))
    with open(game_dir / "game_info.jsonl.log", "r") as f:
        line = f.readline()
        game_log.game_info = GameInfo.from_json(line)
    if (game_dir / "config.json").exists():
        with open(game_dir / "config.json", "r") as f:
            game_log.config = orjson.loads(f.read())
    return web.json_response(json.loads(game_log.to_json()))


@routes.get('/data/username_from_id/{user_id}')
async def GetUsername(request):
    user_id = request.match_info.get('user_id')
    if not user_id:
        return web.HTTPNotFound()

    hashed_id = hashlib.md5(user_id.encode('utf-8')).hexdigest(), # Worker ID is PII, so only save the hash.
    worker_select = schemas.mturk.Worker.select().where(schemas.mturk.Worker.hashed_id == hashed_id)
    if worker_select.count() != 1:
        return web.HTTPNotFound()
    worker = worker_select.get()
    username = leaderboard.LookupUsername(worker)
    return web.json_response({"username": username})

@routes.get('/data/username_from_hash/{hashed_id}')
async def GetUsername(request):
    hashed_id = request.match_info.get('hashed_id')
    if not hashed_id:
        return web.HTTPNotFound()

    worker_select = schemas.mturk.Worker.select().where(schemas.mturk.Worker.hashed_id == hashed_id)
    if worker_select.count() != 1:
        return web.HTTPNotFound()
    worker = worker_select.get()
    username = leaderboard.LookupUsername(worker)
    return web.json_response({"username": username})

@routes.get('/data/leaderboard')
async def MessagesFromServer(request):
    board = leaderboard.GetLeaderboard()
    leaderboard_entries = []
    for i, entry in enumerate(board):
        leader_name = leaderboard.LookupUsername(entry.leader)
        follower_name = leaderboard.LookupUsername(entry.follower)
        if leader_name == None:
            leader_name = ""
        if follower_name == None:
            follower_name = ""
        print(f"{i:3}: scr: {entry.score} ldr: {leader_name} flwr: {follower_name} time: {entry.time}")
        entry = {
            "time": str(entry.time.date()),
            "score": entry.score,
            "leader": leader_name,
            "follower": follower_name,
        }
        leaderboard_entries.append(entry)
    return web.json_response(leaderboard_entries)



@routes.get('/data/messages_from_server/{game_id}')
async def MessagesFromServer(request):
    if not request.match_info.get('game_id'):
        return web.HTTPNotFound()
    game_dir = FindGameDirectory(request.match_info['game_id'])
    if not game_dir:
        return web.HTTPNotFound()
    return web.FileResponse(game_dir / "messages_from_server.json")

@routes.get('/data/messages_to_server/{game_id}')
async def MessagesToServer(request):
    if not request.match_info.get('game_id'):
        return web.HTTPNotFound()
    game_dir = FindGameDirectory(request.match_info['game_id'])
    if not game_dir:
        return web.HTTPNotFound()
    return web.FileResponse(game_dir / "messages_to_server.json")

download_requested = False
download_contents = None
download_status = {
    "status": "idle",
    "log": [],
}
async def DataDownloader(room_manager):
    global download_contents
    global download_requested
    global download_status
    NYC = tz.gettz('America/New_York')
    timestamp =  lambda : datetime.now(NYC).strftime("%Y-%m-%d %H:%M:%S")
    log_entry = lambda x: download_status["log"].append(f"{timestamp()}: {x}")
    while True:
        await asyncio.sleep(1)

        if not download_requested:
            continue

        # Don't process downloads if someone is actively playing a game.
        if len(room_manager.room_ids()) > 0:
            download_status["status"] = "busy"
            log_entry(f"Waiting on {len(room_manager.room_ids())} active games to finish before downloading.")
            await asyncio.sleep(10)
            continue

        database = CSqliteExtDatabase(GlobalConfig().database_path(), pragmas =
                [ ('cache_size', -1024 * 64),  # 64MB page-cache.
                ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
                ('foreign_keys', 1)])
        log_entry(f"Starting...") 
        download_status["status"] = "preparing"
        database.backup_to_file(GlobalConfig().backup_database_path())
        log_entry(f"DB backed up.")
        await asyncio.sleep(0.5)
        time_string = datetime.now().strftime("%Y-%m-%dT%Hh.%Mm.%Ss%z")
        game_archive = shutil.make_archive(f"{GlobalConfig().record_directory()}-{time_string}", 'gztar', GlobalConfig().record_directory())
        log_entry("Game files archived.")
        await asyncio.sleep(0.5)
        download_contents = io.BytesIO()
        with zipfile.ZipFile(download_contents, "a", False) as zip_file:
            with open(GlobalConfig().backup_database_path(), "rb") as db_file:
                zip_file.writestr("game_data.db", db_file.read())
                log_entry(f"DB file added to download ZIP.")
                await asyncio.sleep(0.5)
            with open(game_archive, "rb") as game_file:
                zip_file.writestr("game_record.zip", game_file.read())
                log_entry(f"Game archive added to download ZIP.")
                await asyncio.sleep(0.5)
        # Delete the game archive now that we've read it into memory and added it to the zip file.
        os.remove(game_archive)
        log_entry("Download ready.")
        download_status["status"] = "ready"
        download_requested = False

@routes.get('/data/download_status')
async def DownloadStatus(request):
    global download_status
    return web.json_response(download_status)

@routes.get('/data/download_retrieve')
async def RetrieveData(request):
    global download_contents
    global download_status
    NYC = tz.gettz('America/New_York')
    timestamp =  lambda : datetime.now(NYC).strftime("%Y-%m-%d %H:%M:%S")
    log_entry = lambda x: download_status["log"].append(f"{timestamp()}: {x}")
    local_download_contents = download_contents
    if local_download_contents is None:
        log_entry("Retrieval attempted, but no download available.")
        return web.HTTPNotFound()
    log_entry("Retrieved.")
    download_status["status"] = "done"
    return web.Response(body=local_download_contents.getvalue(), content_type="application/gzip")

@routes.get('/data/download')
async def DataDownloadStart(request):
    global download_requested
    download_requested = True
    download_contents = None
    return web.FileResponse("www/download.html")

@routes.get('/data/game-list')
async def GameList(request):
    games = (schemas.game.Game.select()
                .join(schemas.mturk.Worker, join_type=peewee.JOIN.LEFT_OUTER, on=((schemas.game.Game.leader == schemas.mturk.Worker.id) or (schemas.game.Game.follower == schemas.mturk.Worker.id)))
                .join(schemas.mturk.Assignment, on=((schemas.game.Game.lead_assignment == schemas.mturk.Assignment.id) or (schemas.game.Game.follow_assignment == schemas.mturk.Assignment.id)), join_type=peewee.JOIN.LEFT_OUTER)
                .order_by(schemas.game.Game.id.desc()))
    response = []
    # For convenience, convert timestamps to US eastern time.
    NYC = tz.gettz('America/New_York')
    for game in games:
        response.append({
            "id": game.id,
            "type": game.type,
            "leader": game.leader.hashed_id if game.leader else None,
            "follower": game.follower.hashed_id if game.follower else None,
            "score": game.score,
            "turns": game.number_turns,
            "start_time": str(game.start_time.replace(tzinfo=tz.tzutc()).astimezone(NYC)),
            "duration": str(game.end_time - game.start_time),
            "completed": game.completed,
            "research_valid": db_utils.IsGameResearchData(game)
        })
    return web.json_response(response)

@routes.get('/view/games')
async def GamesViewer(request):
    return web.FileResponse("www/games_viewer.html")

@routes.get('/view/game/{game_id}')
async def GameViewer(request):
    # Extract the game_id from the request.
    return web.FileResponse("www/game_viewer.html")

@routes.get('/data/config')
async def GetConfig(request):
    pretty_dumper = lambda x: orjson.dumps(x, option=orjson.OPT_NAIVE_UTC | orjson.OPT_INDENT_2).decode('utf-8')
    return web.json_response(GlobalConfig(), dumps=pretty_dumper)

@routes.get('/view/stats')
async def Stats(request):
    return web.FileResponse("www/stats.html")

@routes.get('/data/turns/{game_id}')
async def GameData(request):
    game_id = request.match_info.get('game_id')
    game = schemas.game.Game.select().join(schemas.game.Turn, join_type=peewee.JOIN.LEFT_OUTER).where(schemas.game.Game.id == game_id).get()
    turns = []
    # For convenience, convert timestamps to US eastern time.
    NYC = tz.gettz('America/New_York')
    for turn in game.turns:
        turns.append({
            "id": turn.id,
            "number": turn.turn_number,
            "time": str(turn.time.replace(tzinfo=tz.tzutc()).astimezone(NYC)),
            "notes": turn.notes,
            "end_method": turn.end_method,
        })
    return web.json_response(turns)

@routes.get('/data/instructions/{turn_id}')
async def GameData(request):
    turn_id = request.match_info.get('turn_id')
    turn = schemas.game.Turn.select().join(schemas.game.Game).where(schemas.game.Turn.id == turn_id).get()
    game = turn.game
    instructions = schemas.game.Instruction.select().join(schemas.game.Game, join_type=peewee.JOIN.LEFT_OUTER).where(schemas.game.Instruction.turn_issued == turn.turn_number, schemas.game.Instruction.game == game).order_by(schemas.game.Instruction.turn_issued)
    NYC = tz.gettz('America/New_York')
    json_instructions = []
    for instruction in instructions:
        json_instructions.append({
            "instruction_number": instruction.instruction_number,
            "turn_issued": instruction.turn_issued,
            "time": str(instruction.time.replace(tzinfo=tz.tzutc()).astimezone(NYC)),
            "turn_completed": instruction.turn_completed,
            "text": instruction.text
        })
    return web.json_response(json_instructions)

@routes.get('/data/moves/{turn_id}')
async def GameData(request):
    turn_id = request.match_info.get('turn_id')
    turn = schemas.game.Turn.select().join(schemas.game.Game).where(schemas.game.Turn.id == turn_id).get()
    game = turn.game
    moves = schemas.game.Move.select().join(schemas.game.Instruction, join_type=peewee.JOIN.LEFT_OUTER).join(schemas.game.Game, join_type=peewee.JOIN.LEFT_OUTER).where(schemas.game.Move.turn_number == turn.turn_number, schemas.game.Move.game == game.id).order_by(schemas.game.Move.game_time)
    json_moves = []
    for move in moves:
        json_moves.append({
            "character_role": move.character_role,
            "action_code": move.action_code,
            "game_time": move.game_time,
            "position_before": str(move.position_before),
            "instruction": move.instruction.text if move.instruction else "",
        })
    return web.json_response(json_moves)

@routes.get('/data/stats')
async def stats(request):
    games = db_utils.ListResearchGames()
    if len(GlobalConfig().analysis_game_id_ranges) > 0:
        valid_ids = set(itertools.chain(*[range(x, y) for x,y in GlobalConfig().analysis_game_id_ranges]))
        print(f"Filtered to {valid_ids}")
        print(f"Number of valid IDs: {len(valid_ids)}")
        games = [game for game in games if game.id in valid_ids]
    durations = []
    scores = []
    instruction_counts = []
    instructions = []
    instruction_move_counts = []
    vocab = set()
    for game in games:
        for instruction in game.instructions:
            instruction_move_counts.append(instruction.moves.count())
            instructions.append(instruction.text)
            words = instruction.text.split(" ")
            for word in words:
                vocab.add(word)
        duration = (game.end_time - game.start_time).total_seconds()
        score = game.score
        durations.append(duration)
        scores.append(score)
        instruction_counts.append(game.instructions.count())
    
    instruction_word_count = [len(instruction.split(" ")) for instruction in instructions]

    json_stats = []
    json_stats.append({
        "name": "Total Game Time(m:s)",
        "mean": str(timedelta(seconds=statistics.mean(durations))),
        "median": str(timedelta(seconds=statistics.median(durations))),
        "max": str(timedelta(seconds=max(durations)))
    })
    
    json_stats.append( {
        "name": "Score",
        "mean": statistics.mean(scores),
        "median": statistics.median(scores),
        "max": max(scores),
    })

    json_stats.append( {
        "name": "Instructions/Game",
        "mean": statistics.mean(instruction_counts),
        "median": statistics.median(instruction_counts),
        "max": max(instruction_counts)
    })

    json_stats.append( {
        "name": "Tokens/Instruction",
        "mean": statistics.mean(instruction_word_count),
        "median": statistics.median(instruction_word_count),
        "max": max(instruction_word_count)
    })

    json_stats.append( {
        "name": "Follower Actions/Instruction",
        "mean": statistics.mean(instruction_move_counts),
        "median": statistics.median(instruction_move_counts),
        "max": max(instruction_move_counts)
    })

    json_stats.append({
        "name": "Games",
        "count": len(games)
    })

    json_stats.append({
        "name": "Vocabulary Size",
        "count": len(vocab)
    })

    return web.json_response(json_stats)


async def stream_game_state(request, ws):
    global room_manager
    was_in_room = False
    remote = GetRemote(ws)
    remote.last_ping = datetime.now(timezone.utc)
    last_loop = time.time()
    while not ws.closed:
        await asyncio.sleep(0)
        poll_period = time.time() - last_loop
        if (poll_period) > 0.1:
            logging.warn(
                f"Transmit socket for iphash {remote.hashed_ip} port {remote.client_port}, slow poll period of {poll_period}s")
        last_loop = time.time()
        # If not in a room, drain messages from the room manager.
        message = room_manager.drain_message(ws)
        if message is not None:
            await transmit_bytes(ws, orjson.dumps(message, option=orjson.OPT_NAIVE_UTC))

        if not room_manager.socket_in_room(ws):
            if was_in_room:
                logger.info(f"Socket has disappeared after initialization. Ending connection.")
                await ws.close()
                return
            continue

        (room_id, player_id, role) = astuple(room_manager.socket_info(ws))
        room = room_manager.get_room(room_id)

        if room is None:
            logger.warn(f"Room does not exist but room_manager.socket_in_room(ws) returned true.")
            continue

        if not was_in_room:
            was_in_room = True
            # Make sure we drain pending room manager commands here with sleeps to ensure the client has time to switch scenes.
            # await asyncio.sleep(1.0)
            message = room_manager.drain_message(ws)
            if message is not None:
                await transmit_bytes(ws, orjson.dumps(message, option=orjson.OPT_NAIVE_UTC))
            # await asyncio.sleep(1.0)
            continue
        
        # Send a ping every 10 seconds.
        if (datetime.now(timezone.utc) - remote.last_ping).total_seconds() > 10.0:
            remote.last_ping = datetime.now(timezone.utc)
            await transmit_bytes(ws, orjson.dumps(message_from_server.PingMessageFromServer(), option=orjson.OPT_NAIVE_UTC))

        msg_from_server = room.drain_message(player_id)
        while msg_from_server is not None:
            await transmit_bytes(ws, orjson.dumps(msg_from_server, option=orjson.OPT_NAIVE_UTC))
            msg_from_server = room.drain_message(player_id)


async def receive_agent_updates(request, ws):
    global room_manager
    last_loop = time.time()
    async for msg in ws:
        remote = GetRemote(ws)
        poll_period = time.time() - last_loop
        if (poll_period) > 0.1:
            logging.warn(
                f"Receive socket for iphash {remote.hashed_ip} port {remote.client_port}, slow poll period of {poll_period}s")
        last_loop = time.time()
        if ws.closed:
            return
        if msg.type == aiohttp.WSMsgType.ERROR:
            closed = True
            await ws.close()
            print('ws connection closed with exception %s' % ws.exception())
            continue

        if msg.type != aiohttp.WSMsgType.TEXT:
            continue

        remote.last_message_up = time.time()
        remote.bytes_up += len(msg.data)

        if msg.data == 'close':
            closed = True
            await ws.close()
            continue

        logger.debug("Raw message: " + msg.data)
        message = message_to_server.MessageToServer.from_json(msg.data)

        if message.type == message_to_server.MessageType.ROOM_MANAGEMENT:
            room_manager.handle_request(message, ws)
            continue
            
        if message.type == message_to_server.MessageType.PONG:
            # Calculate the time offset.
            t0 = remote.last_ping
            t1 = parser.isoparse(message.pong.ping_receive_time)
            t2 = message.transmit_time
            t3 = datetime.now(timezone.utc)
            # Calculate clock offset and latency.
            remote.time_offset = ((t1 - t0).total_seconds() + (t2 - t3).total_seconds()) / 2
            remote.latency = ((t3 - t0).total_seconds() - (t2 - t1).total_seconds()) / 2
            continue

        if room_manager.socket_in_room(ws):
            # Only handle in-game actions if we're in a room.
            (room_id, player_id, _) = astuple(room_manager.socket_info(
                ws))
            room = room_manager.get_room(room_id)
            room.handle_packet(player_id, message)
        else:
            # Room manager handles out-of-game requests.
            room_manager.handle_request(message, ws)

@routes.get('/player_endpoint')
async def PlayerEndpoint(request):
    global room_manager
    assignment = None
    if "assignmentId" in request.query:
        # If this is an mturk task, log assignment into to the remote table.
        assignment_id = request.query.getone("assignmentId", "")
        hit_id = request.query.getone("hitId", "")
        submit_to_url = request.query.getone("turkSubmitTo", "")
        worker_id = request.query.getone("workerId", "")
        worker, _ = schemas.mturk.Worker.get_or_create(
            hashed_id = hashlib.md5(worker_id.encode('utf-8')).hexdigest(), # Worker ID is PII, so only save the hash.
        )
        assignment, _ = schemas.mturk.Assignment.get_or_create(
            assignment_id=assignment_id,
            worker=worker,
            hit_id=hit_id,
            submit_to_url=submit_to_url
        )

    ws = web.WebSocketResponse(autoclose=True, heartbeat=20.0, autoping=True)
    await ws.prepare(request)
    logger = logging.getLogger()
    logger.info("player connected from : " + request.remote)
    hashed_ip = "UNKNOWN"
    peername = request.transport.get_extra_info('peername')
    port = 0
    if peername is not None:
        ip = peername[0]
        port = peername[1]
        hashed_ip = hashlib.md5(ip.encode('utf-8')).hexdigest()
    remote = Remote(hashed_ip, port, 0, 0, time.time(), time.time(), request, ws)
    AddRemote(ws, remote, assignment)
    LogConnectionEvent(remote, "Connected to Server.")
    try:
        await asyncio.gather(receive_agent_updates(request, ws), stream_game_state(request, ws))
    finally:
        logger.info("player disconnected from : " + request.remote)
        LogConnectionEvent(remote, "Disconnected from Server.")
        room_manager.disconnect_socket(ws)
        DeleteRemote(ws)
    return ws

def HashCollectAssets(assets_directory):
    assets_map = {}
    assets_directory.mkdir(parents=False, exist_ok=True)
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


async def serve(config):
    app = web.Application()

    # Add a route for serving web frontend files on /.
    routes.static('/', './www/WebGL')

    app.add_routes(routes)
    runner = runner = aiohttp.web.AppRunner(app, handle_signals=True)
    await runner.setup()
    site = web.TCPSite(runner, None, config.http_port)
    await site.start()

    print("======= Serving on {site.name} ======".format(site=site))

    # pause here for very long time by serving HTTP requests and
    # waiting for keyboard interruption
    while True:
        await asyncio.sleep(1)


async def draw_gui():
    global room_manager
    room = room_manager.get_room_by_name("Room #0")
    display = visualize.GameDisplay(SCREEN_SIZE)
    while True:
        await asyncio.sleep(0)
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


def InitPythonLogging():
    """  Server logging intended for debugging a server crash.
    
    The server log includes the following, interlaced:
    - Events from each game room.
    - HTTP connection, error & debug information from aiohttp.
    - Misc other server logs (calls to logger.info()).
    - Exception stack traces."""
    log_format = "[%(asctime)s] %(name)s %(levelname)s [%(module)s:%(funcName)s:%(lineno)d] %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)
    logging.getLogger("asyncio").setLevel(logging.INFO)


def InitGameRecording(config):
    """ Game recording allows us to record and later playback individual games.

    Games are saved both in a directory with easily human-readable images and in
    an sqlite3 database.
    
    Each game is given a game id. Logs for a single game are stored in a
    directory with a name of the form: 

    game_records/<datetime>_<game_id>_<game_type>/...

    where <datetime> is in iso8601 format.
    <game_id> can be used to lookup the game in the database.
    <game_type> is GAME or TUTORIAL."""
    record_base_dir = pathlib.Path(config.record_directory())

    # Create the directory if it doesn't exist.
    record_base_dir.mkdir(parents=False, exist_ok=True)

    # Register the logging directory with the room manager.
    room_manager.register_game_logging_directory(record_base_dir)

    # Setup the sqlite database used to record game actions.
    base.SetDatabase(config.database_path())
    base.ConnectDatabase()
    base.CreateTablesIfNotExists(schemas.defaults.ListDefaultTables())
    

# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadConfigOrDie(config_path):
    with open(config_path, 'r') as cfg_file:
        config = Config.from_json(cfg_file.read())
        return config

def CreateDataDirectory(config):
    data_prefix = pathlib.Path(config.data_prefix).expanduser()

    # Create the directory if it doesn't exist.
    data_prefix.mkdir(parents=False, exist_ok=True)

async def profiler():
    last_print = datetime.now()
    while True:
        await asyncio.sleep(1)
        if datetime.now() - last_print > timedelta(seconds=10):
            # print(f"====== Profiler ======")
            # yappi.get_func_stats().print_all()
            # yappi.get_thread_stats().print_all()
            last_print = datetime.now()

def main(config_filepath="config/server-config.json"):
    global assets_map
    global room_manager

    InitPythonLogging()

    InitGlobalConfig(config_filepath)

    logger.info(f"Config file parsed.");
    logger.info(f"data prefix: {GlobalConfig().data_prefix}")
    logger.info(f"Log directory: {GlobalConfig().record_directory()}")
    logger.info(f"Assets directory: {GlobalConfig().assets_directory()}")
    logger.info(f"Database path: {GlobalConfig().database_path()}")

    CreateDataDirectory(GlobalConfig())
    InitGameRecording(GlobalConfig())

    # yappi.set_clock_type("cpu") # Use set_clock_type("wall") for wall time
    # yappi.start()

    assets_map = HashCollectAssets(GlobalConfig().assets_directory())
    tasks = asyncio.gather(room_manager.matchmake(), room_manager.cleanup_rooms(), serve(GlobalConfig()), MapGenerationTask(room_manager, GlobalConfig()), DataDownloader(room_manager))
    # If map visualization command line flag is enabled, run with the visualize task.
    # if gui:
    #   tasks = asyncio.gather(tasks, draw_gui())
    loop = asyncio.get_event_loop()
    # loop.set_debug(enabled=True)
    try:
        loop.run_until_complete(tasks)
    except KeyboardInterrupt:
        pass
    finally:
        room_manager.end_server()
        loop.close()
        
        # yappi.stop()

        # Export a pstats file.
        # yappi.get_func_stats().save('yappi.pstat', type='pstat')
        # yappi.get_func_stats().print_all()
        # yappi.get_thread_stats().print_all()


if __name__ == "__main__":
    fire.Fire(main)
