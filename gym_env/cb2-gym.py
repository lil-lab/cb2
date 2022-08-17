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

from server.util import GetCommitHash
from server.map_tools.visualize import GameDisplay

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

class CerealBar2Env(gym.Env):
  metadata = {"render_modes": ["human", "ascii"], "render_fps": 4}
  """ Implements an OpenAI Gym environment with a CB2 state machine.

  All drained messages and state updates are converted to gym spaces objects.
  The pygame board visualizer is used for rendering.

  """
  def __init__(self, render_mode: Optional[str] = None):
    assert render_mode is None or render_mode in self.metadata["render_modes"]
    self.render_mode = render_mode

    self.visualizer = None

    if self.render_mode == "human":
        self.visualizer = GameDisplay(screen_size=512)

    # Setup database logs.
    game_record = schemas.game.Game()
    game_record.save()
    game_record.log_directory = ""
    game_record.server_software_commit = GetCommitHash()
    game_record.save()

    self.state = state.State(uuid.SafeUUID(bytes=uuid.uuid4().bytes), game_record)
    self.leader_id = self.state.create_actor(state.Role.LEADER)
    self.follower_id = self.state.create_actor(state.Role.FOLLOWER)

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