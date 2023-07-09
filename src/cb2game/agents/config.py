""" Defines config for configuring CB2 agents. """
import dataclasses
import importlib
import inspect
import logging
from enum import Enum
from typing import Optional

import yaml
from mashumaro.mixins.json import DataClassJSONMixin

from cb2game.agents.agent import Agent
from cb2game.agents.gpt_follower import GptFollower, GptFollowerConfig
from cb2game.agents.simple_follower import SimpleFollower, SimpleFollowerConfig
from cb2game.agents.simple_leader import SimpleLeader
from cb2game.util.deprecated import deprecated

logger = logging.getLogger(__name__)


@deprecated("Use AgentConfigData and LoadAgentFromConfig() instead.")
class AgentType(Enum):
    NONE = 0
    # Follower used for CB2 pilot study.
    PILOT_FOLLOWER = 1
    # Experimental follower that uses a text-only interface to OpenAI's GPT API.
    GPT_FOLLOWER = 2
    # Simple follower/leader for unit testing and debugging.
    SIMPLE_FOLLOWER = 3
    SIMPLE_LEADER = 4

    def __str__(self):
        return self.name

    @staticmethod
    def from_str(s: str):
        return AgentType[s]


@deprecated("Use AgentConfigData and LoadAgentFromConfig() instead.")
class AgentConfig(DataClassJSONMixin):
    name: str
    comment: str
    # agent_type must be one of the values in enum AgentType.
    agent_type: str

    gpt_follower_config: Optional[GptFollowerConfig] = None
    """Configuration for initializing a GptFollower agent."""
    simple_follower_config: Optional[SimpleFollowerConfig] = None
    """Configuration for initializing a SimpleFollower agent."""


@dataclasses.dataclass
class AgentConfigData:
    type: str
    config_type: str
    config: dict


# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadAgentConfigOrDie(config_path) -> AgentConfig:
    with open(config_path, "r") as cfg_file:
        data = yaml.load(cfg_file, Loader=yaml.CLoader)
        config = AgentConfig.from_dict(data)
        return config


@deprecated("Use AgentConfigData and LoadAgentFromConfig() instead.")
def CreateAgent(config: AgentConfig) -> Agent:
    agent_type = AgentType.from_str(config.agent_type)
    if agent_type == AgentType.NONE:
        return None
    elif agent_type == AgentType.PILOT_FOLLOWER:
        # TODO: Implement PilotFollower agent.
        return None
    elif agent_type == AgentType.GPT_FOLLOWER:
        return GptFollower(config.gpt_follower_config)
    elif agent_type == AgentType.SIMPLE_FOLLOWER:
        return SimpleFollower(config.simple_follower_config)
    elif agent_type == AgentType.SIMPLE_LEADER:
        return SimpleLeader()


def LoadAgentFromConfig(config_file_path: str):
    # Load the configuration file.
    with open(config_file_path, "r") as file:
        config_data = yaml.safe_load(file)

    # Extract the module and class names.
    class_path = config_data["my_agent"]["type"].split(".")
    module_name, class_name = ".".join(class_path[:-1]), class_path[-1]

    if module_name:
        # If module_name is not empty, import the module and get the class.
        module = importlib.import_module(module_name)
        class_ = getattr(module, class_name)
    else:
        # If module_name is empty, assume the class is in the current namespace.
        globals_, locals_ = globals(), locals()
        class_ = locals_.get(class_name, globals_.get(class_name))

    # Extract the config class from the first argument type hint of the Agent's constructor
    signature = inspect.signature(class_.__init__)
    if "config" not in signature.parameters:
        raise ValueError("Agent's constructor doesn't have a 'config' parameter")

    config_class = signature.parameters["config"].annotation
    if config_class == inspect._empty:
        raise ValueError(
            "Agent's constructor doesn't have a type hint for the 'config' parameter"
        )

    # Create an instance of the config class using the configuration data.
    config_instance = config_class(**config_data["my_agent"]["config"])

    # Create an instance of the agent class using the configuration instance.
    instance = class_(config_instance)

    return instance
