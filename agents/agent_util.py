from agents.agent import Agent, AgentType
from agents.config import AgentConfig
from agents.gpt_follower import GPTFollower


def CreateAgent(config: AgentConfig) -> Agent:
    agent_type = AgentType.from_str(config.agent_type)
    if agent_type == AgentType.NONE:
        return None
    elif agent_type == AgentType.PILOT_FOLLOWER:
        # TODO: Implement PilotFollower agent.
        return None
    elif agent_type == AgentType.GPT_FOLLOWER:
        return GPTFollower(config.gpt_follower_config)
