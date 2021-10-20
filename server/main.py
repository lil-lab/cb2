import aiohttp
import asyncio
import fire
import hashlib
import json
import os
import time

from aiohttp import web
from messages import map_update
from messages import message_from_server
from messages import message_to_server
from messages import state_sync
from hex import HecsCoord, HexBoundary, HexCell

from datetime import datetime

routes = web.RouteTableDef()

# A table of active websocket connections.
remote_table = {}

@routes.get('/')
async def Index(request):
  global assets_map
  global remote_table
  server_state = {
    "assets": assets_map,
    "endpoints": remote_table,
  }
  return web.json_response(server_state)

async def stream_game_state(request, ws, agent_id):
  # mupdate = map_update.MapUpdate(20, 20, [map_update.Tile(1, HexCell(HecsCoord(1, 3, 7)))])
  await asyncio.sleep(0.1)
  sync = state_sync.StateSync([state_sync.Actor(2, 1, HecsCoord(0, 3, 7), 0)], 1)
  message = message_from_server.MessageFromServer(datetime.now(), message_from_server.MessageType.STATE_SYNC, None, None, sync)
  print("Sending...: " + message.to_json())
  await ws.send_str(message.to_json())
  return
  global remote_table
  while not ws.closed:
    await asyncio.sleep(0.1)
    remote_table[request.remote]["bytes_down"] += len(json.dumps(state))

async def receive_agent_updates(request, ws, agent_id):
  global remote_table
  async for msg in ws:
    if msg.type == aiohttp.WSMsgType.ERROR:
      closed = True
      await ws.close()
      del remote_table[request.remote]
      print('ws connection closed with exception %s' % ws.exception())
      continue

    if msg.type != aiohttp.WSMsgType.TEXT:
      continue

    remote_table[request.remote]["last_message_up"] = time.time()
    remote_table[request.remote]["bytes_up"] += len(msg.data)

    if msg.data == 'close':
      closed = True
      await ws.close()
      del remote_table[request.remote]
      continue

    message = message_to_server.MessageToServer.from_json(msg.data)
    if message.type == message_to_server.MessageType.ACTIONS:
      print("Action received. Transmit: {0}, Type: {1}, Actions:")
      for action in message.actions:
        print("{0}:{1}".format(action.actor_id, action.destination))
    remote_table[request.remote]["last_message_down"] = time.time()

def max_agent_id():
  global remote_table
  max_id = 0
  for remote in remote_table:
    if remote_table[remote]["id"] > max_id:
      max_id = remote_table[remote]["id"]
  return max_id


@routes.get('/player_endpoint')
async def PlayerEndpoint(request):
  global remote_table
  ws = web.WebSocketResponse()
  await ws.prepare(request)
  remote_table[request.remote] = {"last_message_up": time.time(), "last_message_down": time.time(), "ip": request.remote, "id":0, "bytes_up": 0, "bytes_down": 0}
  agent_id = max_agent_id() + 1
  remote_table[request.remote]["id"] = agent_id
  await asyncio.gather(receive_agent_updates(request, ws, agent_id), stream_game_state(request, ws, agent_id))
  del remote_table[request.remote]
  return ws

def CollectAssets(assets_directory):
  assets_map = {}
  for item in os.listdir(assets_directory):
    assets_map[hashlib.md5(item.encode()).hexdigest()] = os.path.join(assets_directory, item)
  return assets_map

# A dictionary from md5sum to asset filename.
assets_map = {}

@routes.get('/assets/{asset_id}')
async def asset(request):
  asset_id = request.match_info.get('asset_id', "")
  if (asset_id not in assets_map):
    raise aiohttp.web.HTTPNotFound('/redirect')
  return web.FileResponse(assets_map[asset_id])

async def serve():
  app = web.Application()
  app.add_routes(routes)
  runner = runner = aiohttp.web.AppRunner(app)
  await runner.setup()
  site = web.TCPSite(runner, 'localhost', 8080)
  await site.start()

  print("======= Serving on http://127.0.0.1:8080/ ======")

  # pause here for very long time by serving HTTP requests and
  # waiting for keyboard interruption
  while True:
    await asyncio.sleep(1)

def main(assets_directory = "assets/"):
  global assets_map
  global game_state
  # game_state_task = asyncio.gather(game_state.loop())
  assets_map = CollectAssets(assets_directory)
  loop = asyncio.get_event_loop()

  try:
      loop.run_until_complete(serve())
  except KeyboardInterrupt:
      pass
  loop.close()

if __name__ == "__main__":
  fire.Fire(main)
