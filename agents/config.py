""" Defines config for configuring CB2 agents. """
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import yaml
from mashumaro.mixins.json import DataClassJSONMixin

from agents.agent import Agent
from agents.gpt_follower import GPTFollower, GPTFollowerConfig
from agents.simple_follower import SimpleFollower, SimpleFollowerConfig
from agents.simple_leader import SimpleLeader


class AgentType(Enum):
    NONE = 0
    PILOT_FOLLOWER = 1
    GPT_FOLLOWER = 2
    SIMPLE_FOLLOWER = 3
    SIMPLE_LEADER = 4

    def __str__(self):
        return self.name

    @staticmethod
    def from_str(s: str):
        return AgentType[s]


@dataclass
class AgentConfig(DataClassJSONMixin):
    name: str
    comment: str
    # agent_type must be one of the values in enum AgentType.
    agent_type: str

    gpt_follower_config: Optional[GPTFollowerConfig] = None
    """Configuration for initializing a GPTFollower agent."""
    simple_follower_config: Optional[SimpleFollowerConfig] = None
    """Configuration for initializing a SimpleFollower agent."""


# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadAgentConfigOrDie(config_path) -> AgentConfig:
    with open(config_path, "r") as cfg_file:
        data = yaml.load(cfg_file, Loader=yaml.CLoader)
        config = AgentConfig.from_dict(data)
        return config


def CreateAgent(config: AgentConfig) -> Agent:
    agent_type = AgentType.from_str(config.agent_type)
    if agent_type == AgentType.NONE:
        return None
    elif agent_type == AgentType.PILOT_FOLLOWER:
        # TODO: Implement PilotFollower agent.
        return None
    elif agent_type == AgentType.GPT_FOLLOWER:
        return GPTFollower(config.gpt_follower_config)
    elif agent_type == AgentType.SIMPLE_FOLLOWER:
        return SimpleFollower(config.simple_follower_config)
    elif agent_type == AgentType.SIMPLE_LEADER:
        return SimpleLeader()
