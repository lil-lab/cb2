import string
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import gym
import numpy as np
from gym import register, spaces

import server.assets as assets
import server.card as card
import server.hex as hex
import server.messages.live_feedback as live_feedback
import server.messages.prop as prop
import server.state as state
from py_client.endpoint_pair import EndpointPair
from py_client.local_game_coordinator import LocalGameCoordinator
from py_client.remote_client import RemoteClient
from server.map_provider import MAP_HEIGHT, MAP_WIDTH
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
    # Local mode, no server or network connection. Must specify game name.
    LOCAL = 1
    # Remote mode, connect to server and play game. Must specify server URL. May play against a human.
    REMOTE = 2


@dataclass
class AuxiliaryInfo:
    agent_role: Role = Role.NONE
    env_mode: EnvMode = EnvMode.NONE
    server_url: str = ""
    game_name: str = ""
    action_mask: Optional[np.ndarray] = None


DEFAULT_MAX_INSTRUCTION_LENGTH = 1000  # Chars.


class CerealBar2Env(gym.Env):
    metadata = {"render_modes": ["human", "headless"], "render_fps": 4}
    """ Implements an OpenAI Gym environment with a CB2 state machine.

    All drained messages and state updates are converted to gym spaces objects.
    The pygame board visualizer is used for rendering.


    Launching an environment with a local game:
    ```
        coordinator = LocalGameCoordinator()
        game_name = coordinator.CreateGame()
        # Creating the OpenAI environment implicitly calls JoinGame(game_name).
        leader_env = gym.make("CerealBar2-v0", render_mode="human", mode=EnvMode.LOCAL, game_name=game_name, coordinator=coordinator)
        follower_env = gym.make("CerealBar2-v0", render_mode="human", mode=EnvMode.LOCAL, game_name=game_name, coordinator=coordinator)
        leader_agent = ...
        follower_agent = ...
        leader_env_state = leader_env.reset()
        follower_env_state = follower_env.reset()
        while True:
            leader_action = leader_agent(leader_env_state)
            follower_action = follower_agent(follower_env_state)
            leader_env_state, leader_reward, leader_done, leader_info = leader_env.step(leader_action)
            follower_env_state, follower_reward, follower_done, follower_info = follower_env.step(follower_action)
            if leader_done or follower_done:
                break
        # The game is over, so we can clean up the state machine.
        coordinator.Cleanup()
    ```

        Launching an environment with a remote game:

    ```
        server_url = "http://cb2-server-url.whatever"
        leader_env = gym.make("CerealBar2-v0", render_mode="human", mode=EnvMode.REMOTE, server_url=server_url, server_queue_type=RemoteClient.QueueType.LEADER_ONLY)
        leader_agent = ...
        leader_env_state = leader_env.reset()
        while True:
        leader_action = leader_agent(leader_env_state)
        leader_env_state, leader_reward, leader_done, leader_info = leader_env.step(leader_action)
        follower_env_state, follower_reward, follower_done, follower_info = follower_env.step(follower_action)
        if leader_done or follower_done:
            break
    ```
    """

    def __init__(
        self,
        game_mode: EnvMode = EnvMode.NONE,
        game_name: str = "",
        game_coordinator: Optional[LocalGameCoordinator] = None,
        server_url: str = "",
        server_queue_type: RemoteClient.QueueType = RemoteClient.QueueType.DEFAULT,
        render_mode: Optional[str] = None,
        max_instruction_length: int = DEFAULT_MAX_INSTRUCTION_LENGTH,
    ):
        """CB2 Env Constructor.

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

        REMOTE:
            In this mode, the game is played remotely on a server. It is unknown
            who the other player is (could be a human or another agent), and
            step() will block until a move is possible. This could be quiet a
            while (~1 minute) if playing against a human. If connecting to a
            server, a server_url must be provided.

        Args:
            game_mode: Mode to start the environment in. See above for details.
            game_name: Unique name of the game to play. Required in LOCAL mode.
            game_coordinator: Coordinates multiagent environments in LOCAL mode.
            server_url: URL of the CB2 server. Required in REMOTE mode.
            server_queue_type: Server queue to join (leader/remote/default).
            render_mode: Env display mode. "human" for GUI or None for headless.
            max_instruction_length: Max length of instructions in chars.
        """
        assert render_mode is None or render_mode in self.metadata["render_modes"]
        self.render_mode = render_mode

        self.game_info = AuxiliaryInfo()
        self.game_info.env_mode = game_mode

        self.game_mode = game_mode
        if self.game_mode == EnvMode.LOCAL:
            self.coordinator = game_coordinator
            self.game_name = game_name
            self.game_info.game_name = game_name

        elif self.game_mode == EnvMode.REMOTE:
            self.client = RemoteClient(server_url, self.render_mode == "human")
            self.game_info.server_url = server_url
            self.server_queue_type = server_queue_type

        self.observation_space = spaces.Dict(
            {
                "actors": spaces.Dict(
                    {
                        "leader": spaces.Box(
                            low=np.array([0, 0]),
                            high=np.array([MAP_HEIGHT, MAP_WIDTH]),
                            dtype=np.int16,
                        ),
                        "follower": spaces.Box(
                            low=np.array([0, 0]),
                            high=np.array([MAP_HEIGHT, MAP_WIDTH]),
                            dtype=np.int16,
                        ),
                    }
                ),
                "map": spaces.Dict(
                    {
                        "asset_ids": spaces.Box(
                            low=0,
                            high=int(assets.AssetId.EMPTY_TILE.value),
                            shape=[MAP_HEIGHT, MAP_WIDTH],
                            dtype=np.int16,
                        ),
                        "boundaries": spaces.Box(
                            low=0,
                            high=int(hex.HexBoundary.MAX_VAL),
                            shape=np.array([MAP_HEIGHT, MAP_WIDTH]),
                            dtype=np.int8,
                        ),
                        "orientations": spaces.Box(
                            low=0,
                            high=360,
                            shape=(MAP_HEIGHT, MAP_WIDTH),
                            dtype=np.int16,
                        ),
                    }
                ),
                "cards": spaces.Dict(
                    {
                        "counts": spaces.Box(
                            low=0, high=3, shape=(MAP_HEIGHT, MAP_WIDTH), dtype=np.int8
                        ),
                        "colors": spaces.Box(
                            low=0,
                            high=int(card.Color.MAX.value),
                            shape=(MAP_HEIGHT, MAP_WIDTH),
                            dtype=np.int8,
                        ),
                        "shapes": spaces.Box(
                            low=0,
                            high=int(card.Shape.MAX.value),
                            shape=(MAP_HEIGHT, MAP_WIDTH),
                            dtype=np.int8,
                        ),
                        "selected": spaces.Box(
                            low=0,
                            high=card.SelectedState.MAX.value,
                            shape=(MAP_HEIGHT, MAP_WIDTH),
                            dtype=np.int8,
                        ),
                    }
                ),
                "instructions": spaces.Sequence(
                    spaces.Text(
                        max_length=max_instruction_length,
                        min_length=0,
                        charset=string.printable,
                    )
                ),
                "turn_state": spaces.Dict(
                    {
                        "role": spaces.Discrete(state.Role.MAX.value),
                        "moves_remaining": spaces.Box(
                            low=0, high=65536, shape=(1,), dtype=np.int16
                        ),
                        "turns_remaining": spaces.Box(
                            low=0, high=65536, shape=(1,), dtype=np.int16
                        ),
                        "score": spaces.Box(
                            low=0, high=65536, shape=(1,), dtype=np.int16
                        ),
                    }
                ),
                # Feedback is either positive, negative, or none.
                "feedback": spaces.Discrete(live_feedback.FeedbackType.MAX.value),
            }
        )

        self.lead_action_space = spaces.Dict(
            {
                "action": spaces.Discrete(LeadActions.MAX.value),
                "instructions": spaces.Sequence(
                    spaces.Text(
                        max_length=max_instruction_length,
                        min_length=0,
                        charset=string.printable,
                    )
                ),
            }
        )

        self.follow_action_space = spaces.Dict(
            {
                "action": spaces.Discrete(FollowActions.MAX.value),
            }
        )

        # Start with leader turn.
        self.action_space = self.lead_action_space

    def reset(self):
        """Initializes the environment to the initial state.

        Returns the initial environment state.
        """
        if self.game_mode == EnvMode.LOCAL:
            self.game = EndpointPair(self.coordinator, self.game_name)
            self.game.initialize()
        elif self.game_mode == EnvMode.REMOTE:
            joined, reason = self.client.Connect()
            assert joined, f"Could not join: {reason}"
            self.game = self.client.JoinGame(self.server_queue_type)
        else:
            raise ValueError(f"Invalid game mode: {self.game_mode}")
        return self.gym_state_from_client_state(self.game.initial_state())

    def step(self, action):
        return self.gym_state_from_client_state(self.game.step(action))

    def gym_state_from_client_state(self, state):
        """Converts to OpenAI gym (observation, reward, done, info) from CB2 pyclient state."""
        map_update, props, turn_state, instructions, actors, feedback = state
        (leader, follower) = actors
        actors = {
            "leader": leader.location().to_offset_coordinates(),
            "follower": follower.location().to_offset_coordinates(),
        }
        asset_ids = [
            [assets.AssetId.NONE for _ in range(map_update.cols)]
            for _ in range(map_update.rows)
        ]
        boundaries = [
            [-1 for _ in range(map_update.cols)] for _ in range(map_update.rows)
        ]
        orientations = [
            [0 for _ in range(map_update.cols)] for _ in range(map_update.rows)
        ]
        for tile in map_update.tiles:
            row, col = tile.cell.coord.to_offset_coordinates()
            asset_ids[row][col] = tile.asset_id
            boundaries[row][col] = tile.cell.boundary.edges
            orientations[row][col] = tile.rotation_degrees
        map = {
            "asset_ids": asset_ids,
            "boundaries": boundaries,
            "orientations": orientations,
        }
        card_counts = [
            [0 for _ in range(map_update.cols)] for _ in range(map_update.rows)
        ]
        card_colors = [
            [card.Color.NONE for _ in range(map_update.cols)]
            for _ in range(map_update.rows)
        ]
        card_shapes = [
            [card.Shape.NONE for _ in range(map_update.cols)]
            for _ in range(map_update.rows)
        ]
        card_selected = [
            [False for _ in range(map_update.cols)] for _ in range(map_update.rows)
        ]
        for p in props:
            if p.prop_type == prop.PropType.CARD:
                (row, col) = p.prop_info.location.to_offset_coordinates()
                card_counts[row][col] = p.card_init.count
                card_colors[row][col] = p.card_init.color
                card_shapes[row][col] = p.card_init.shape
                card_selected[row][col] = p.card_init.selected
        cards = {
            "counts": card_counts,
            "colors": card_colors,
            "shapes": card_shapes,
            "selected": card_selected,
        }
        openai_turn_state = {
            "role": turn_state.turn,
            "moves_remaining": [turn_state.moves_remaining],
            "turns_remaining": [turn_state.turns_left],
            "score": [turn_state.score],
        }
        action_mask = self.game.action_mask()
        aux_info = AuxiliaryInfo(
            self.game_info.agent_role,
            self.game_info.env_mode,
            self.game_info.server_url,
            self.game_info.game_name,
            action_mask,
        )
        return (
            {
                "actors": actors,
                "map": map,
                "cards": cards,
                "instructions": instructions,
                "turn_state": openai_turn_state,
                "feedback": feedback,
            },
            turn_state.score,
            turn_state.game_over,
            aux_info,
        )


register(
    id="CerealBar2-v0",
    entry_point="envs.cb2:CerealBar2Env",
    max_episode_steps=10000,  # Should be impossible to reach.
    nondeterministic=False,
    reward_threshold=None,
)
