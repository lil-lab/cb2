""" Defines config for configuring CB2 agents. """
from dataclasses import dataclass
from typing import Optional

import yaml
from mashumaro.mixins.json import DataClassJSONMixin

from agents.gpt_follower import GPTFollowerConfig


@dataclass
class AgentConfig(DataClassJSONMixin):
    name: str
    comment: str
    # agent_type must be one of the values in enum AgentType.
    agent_type: str

    # GPTFollowerConfig
    gpt_follower_config: Optional[GPTFollowerConfig] = None


# Attempts to parse the config file. If there's any parsing or file errors,
# doesn't handle the exceptions.
def ReadAgentConfigOrDie(config_path) -> AgentConfig:
    with open(config_path, "r") as cfg_file:
        data = yaml.load(cfg_file, Loader=yaml.CLoader)
        config = AgentConfig.from_dict(data)
        return config
