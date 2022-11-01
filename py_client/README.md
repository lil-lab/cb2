Python Client API
=================

- [Python Client API](#python-client-api)
  - [Remote Client API](#remote-client-api)
  - [Local Self-play API](#local-self-play-api)
  - [Game Endpoint](#game-endpoint)
  - [Example Bot Implementations](#example-bot-implementations)

Remote Client API
-----------------

The client API lets you write bots which can interact with live users on a CB2 server via `py_client/remote_client.py`.  This API provides routines for entering a queue and waiting for a game. Once a game has been joined, the Remote Client API provides a `GameEndpoint` for interacting with games. See below for more on the game endpoint.
```
client = RemoteClient("http://localhost:8080", render=True)
connected, reason = client.Connect()
assert connected, f"Unable to connect: {reason}"
leader_agent = ...
game, reason = client.JoinGame(queue_type=RemoteClient.QueueType.LEADER_ONLY)
assert game is not None, f"Unable to join game: {reason}"
map, cards, turn_state, instructions, (leader, follower), live_feedback = game.initial_state()
action = leader_agent.get_action(map, cards, turn_state, instructions)
while not game.over():
    map, cards, turn_state, instructions, (leader, follower), live_feedback = game.step(action)
    action = leader_agent.get_action(map, cards, turn_state, instructions)
```

For more realistic examples, see `routing_leader_client.py` and `follower_client.py` in `py_client/demos/`.

Local Self-play API
-------------------

Bots can also be written which play against each other locally, by sending messages directly to an in-process instance of the game state machine. This can be done by using `py_client/local_game_coordinator.py`. Since there are no network sockets used, local games are much higher performance, and testing on my macbook (M1 Pro) has shown that a full game can be played every ~400ms with database logging enabled, and in only 115ms with logging disabled (see parameter `log_to_db` in `coordinator.CreateGame` below).

For local self-play, both bots are controlled through `EndpointPair`, a class which wraps two `GameEndpoint` interfaces. `EndpointPair` is mostly similar to `GameEndpoint`, but you need to call `initialize()` before starting, and for each call to `step()`, you should check `turn_state` to see which agent's turn it is.

```
coordinator = LocalGameCoordinator(ReadConfigOrDie(config_filepath))
game_name = coordinator.CreateGame(log_to_db=log_to_db)
endpoint_pair = EndpointPair(coordinator, game_name)
leader_agent = ...
follower_agent = ...
endpoint_pair.initialize()
map, cards, turn_state, instructions, actors, live_feedback = endpoint_pair.initial_state()
    while not endpoint_pair.over():
        if turn_state.turn == Role.LEADER:
            leader_action = leader_agent.get_action(map, cards, turn_state, instructions, actors, live_feedback)
            map, cards, turn_state, instructions, actors, live_feedback = endpoint_pair.step(leader_action)
        else:
            follower_action = follower_agent.get_action(map, cards, turn_state, instructions, actors, live_feedback)
            map, cards, turn_state, instructions, actors, live_feedback = endpoint_pair.step(follower_action)
```

Game Endpoint
-------------

Both local and remote play interfaces make use of `GameEndpoint` objects, which define the interface for interacting with a single instance of a game.

A game endpoint represents an interface to the game from the perspective of a single player. In the case of local self-play, an `EndpointPair` is created, which wraps two `GameEndpoint` instances in a similar API.

The API is fully defined in `game_endpoint.py`, but here's a rough summary:

```
# Returns initial world state. Can only be called once.
initial_state = game_endpoint.initial_state()

# Returns true if the game is done.
game_over = game_endpoint.over()

# Makes an action, updates world state. Blocks until its the calling agent's
# turn.  In the case of local self-play (EndpointPair), blocks until its
# anyone's turn.
next_state = game_endpoint.step(action)
```

Example Bot Implementations
---------------------------

We provide working implementations of demonstration bots in `py_client/demos/` as further help to the reader. These can be launched from the command line and interacted with.

```
# Launch a 'dumb' follower client. Only responds to CSV instructions like 'forward, left, right, backwards', etc.
python3 -m py_client.demos.follower_client http://localhost:8080

# Launches a path-finding leader which generates CSV instructions for the above follower.
python3 -m py_client.demos.routing_leader_client http://localhost:8080
```

For both of the above commands, a pygame GUI is used to render game state from the agent's perspective. You can enable or disable this with `--render=True` or `--render=False`. You must have a local CB2 server running, see the root directory README for more instructions.
