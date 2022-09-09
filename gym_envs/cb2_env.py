from dataclasses import dataclass
import gym
import numpy as np
import pathlib
import uuid

import server.assets as assets
import server.hex as hex
import server.messages.message_from_server as message_from_server
import server.schemas as schemas
import server.state as state
import server.card as card

from datetime import datetime
from enum import Enum
from gym import spaces
from gym.utils.renderer import Renderer
from typing import Optional

from py_client.cb2_client import Cb2Client
from gym_envs.local_game_coordinator import LocalGameCoordinator
from server.util import GetCommitHash
from server.map_tools.visualize import GameDisplay
from server.messages.rooms import Role

class LeadActions(Enum):
    NONE = 0
    FORWARDS = 1
    BACKWARDS = 2
    TURN_LEFT = 3
    TURN_RIGHT = 4
    END_TURN = 5
    POSITIVE_FEEDBACK = 6
    NEGATIVE_FEEDBACK = 7
    INTERRUPT = 8
    SEND_INSTRUCTION = 9
    MAX = 10

class FollowActions(Enum):
    NONE = 0
    FORWARDS = 1
    BACKWARDS = 2
    TURN_LEFT = 3
    TURN_RIGHT = 4
    INSTRUCTION_DONE = 5
    MAX = 6

class EnvMode(Enum):
    NONE = 0
    LOCAL = 1 # Local mode, no server or network connection. Must specify game name.
    SERVER = 2 # Server mode, connect to server and play game. Must specify server URL. May play against a human.

@dataclass
class AuxiliaryInfo:
    agent_role: Role = Role.NONE
    env_mode: EnvMode = EnvMode.NONE
    server_url: str = ""
    game_name: str = ""

class CerealBar2Env(gym.Env):
  metadata = {"render_modes": ["human"], "render_fps": 4}
  """ Implements an OpenAI Gym environment with a CB2 state machine.

  All drained messages and state updates are converted to gym spaces objects.
  The pygame board visualizer is used for rendering.

  """
  def __init__(
    self,
    game_mode: EnvMode = EnvMode.NONE,
    game_name: str="",
    game_coordinator: Optional[LocalGameCoordinator] = None,
    server_url: str="",
    database_game_id: int=-1,
    database_instruction_uuid: str = "",
    render_mode: Optional[str] = None):
    """ CB2 Env Constructor.
    
        Creates a Cereal Bar 2 OpenAI Gym environment.

        OpenAI gym isn't built for multi-agent play, and CB2 is a two-agent
        game. To make up for this, clients are linked implicitly. There are
        several modes to start a CB2 Environment in:

        LOCAL:
            In this mode, the game is played locally. No network sockets are
            used, and all packets are passed directly as python objects to a CB2
            state machine running in the same process. Because of this, super
            fast games can be achieved. If a game is run locally, a unique
            game_name must be provided (and only two clients can use the same
            game name). This is used to pair with the other client.

            Two agents that use the same game_name will be paired together in
            the same game. It is invalid for more than two agents to use the
            same game_name. The first environment created is always the leader,
            and the second is the follower. This can be verified by checking the
            action_space variable, as it differs for leader and follower.
            
        SERVER:
            In this mode, the game is played remotely on a server. It is unknown
            who the other player is (could be a human or another agent), and
            step() will block until a move is possible. This could be quiet a
            while (~1 minute) if playing against a human. If connecting to a
            server, a server_url must be provided.
            
        Args:
            game_mode: Mode to start the environment in. See above for details.
            game_name: Unique name of the game to play. Required in LOCAL mode.
            game_coordinator: Coordinates multiagent environments in LOCAL mode.
            server_url: URL of the CB2 server. Required in SERVER mode.
            render_mode: Env display mode. "human" for GUI or None for headless.
    """
    assert render_mode is None or render_mode in self.metadata["render_modes"]
    self.render_mode = render_mode

    self.game_info = AuxiliaryInfo()
    self.game_info.env_mode = game_mode

    self.game_mode = game_mode
    if self.game_mode == EnvMode.LOCAL:
        self.coordinator = game_coordinator
        self.game_name = game_name
        self.agent_id = self.coordinator.JoinGame(self.game_name)
        self.game_info.game_name = game_name

    elif self.game_mode == EnvMode.SERVER:
        self.client = Cb2Client(server_url, self.render_mode == "human")
        self.game_info.server_url = server_url

    map = self.state.map()

    self.observation_space = spaces.Dict({
        "actors": spaces.Dict({
            "leader": spaces.Box(low=[0, 0], high=[map.rows, map.cols], dtype=np.int16),
            "follower": spaces.Box(low=[0, 0], high=[map.rows, map.cols], dtype=np.int16),
        }),
        "map": spaces.dict({
            "asset_ids": spaces.Box(low=0, high=assets.AssetId.EMPTY_TILE, shape=(map.rows, map.cols), dtype=np.int16),
            "boundaries": spaces.Box(low=0, high=hex.HexBoundary.MAX_VAL, shape=(map.rows, map.cols), dtype=np.int8),
            "orientations": spaces.Box(low=0, high=360, shape=(map.rows, map.cols), dtype=np.int16),
        }),
        "cards": spaces.Dict({
            "counts": spaces.Box(low=0, high=3, shape=(map.rows, map.cols), dtype=np.int8),
            "colors": spaces.Box(low=0, high=card.Color.MAX, shape=(map.rows, map.cols), dtype=np.int8),
            "shapes": spaces.Box(low=0, high=card.Shape.MAX, shape=(map.rows, map.cols), dtype=np.int8),
            "selected": spaces.Box(low=0, high=card.SelectedState.MAX, shape=(map.rows, map.cols), dtype=np.int8),
        }),
        "instructions": spaces.Box(shape=(1000, 1000), dtype=np.int32),
        "turn_state": spaces.Dict({
            "role": spaces.Discrete(state.Role.MAX),
            "moves_remaining": spaces.Box(shape=(1,), dtype=np.int16),
            "turns_remaining": spaces.Box(shape=(1,), dtype=np.int16),
            "score": spaces.Box(shape=(1,), dtype=np.int16),
        }),
    })

    self.lead_action_space = spaces.Dict({
        "action": spaces.Discrete(LeadActions.MAX),
        "instruction": spaces.Box(shape=(1000, 1000), dtype=np.int32),
    })

    self.follow_action_space = spaces.Dict({
        "action": spaces.Discrete(FollowActions.MAX),
    })

    # Start with leader turn.
    self.action_space = self.lead_action_space
    self.reset()

    def _get_obs(self):
        map = self.state.map()
        return {
            "actors": {
                "leader": self.state.get_actor(self.leader_id).location().to_offset_coordinates(),
                "follower": self.state.get_actor(self.follower_id).location().to_offset_coordinates(),
            },
            "map": {
                "asset_ids": [map[]]
            },
            "cards": {
            },
            "instructions": self.state.instructions(),
        }

    def drain_leader_messages(self):
        message = self.state.drain_message(self.leader_id)
        while message != None:
            message = self.state.drain_message(self.leader_id)
    
    def drain_follower_messages(self):
        message = self.state.drain_message(self.follower_id)
        while message != None:
            message = self.state.drain_message(self.follower_id)

    def drain_messages(self):
        self.drain_leader_messages()
        self.drain_follower_messages()
    
    def step()