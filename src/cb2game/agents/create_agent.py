import os
import time

import fire

from cb2game.util.confgen import MoveFilesOutOfTheWay, StringFromUserInput, slow_type

AGENT_TEMPLATE = """\
\"\"\"This is a template file for creating a new Agent.

Replace the class and method definitions with your own implementations.
\"\"\"

from dataclasses import dataclass

from cb2game.agents.agent import Role, Agent
from cb2game.pyclient.game_endpoint import Action, GameState

@dataclass
class {agent_name}Config(object):
    \"\"\"Configuration for {agent_name}.\"\"\"

    # Add configuration fields here.
    # Then generate the agent config yaml with:
    # `python3 -m cb2game.agents.generate_config {module_name}`
    pass


class {agent_name}(Agent):
    def __init__(self, config: {agent_name}Config):
        # Initialize your agent here.
        self.config = config

    # OVERRIDES role
    def role(self) -> Role:
        # This function should be a one-liner.
        # Return the role of your agent (Role.LEADER or Role.FOLLOWER).
        raise NotImplementedError("Implement this...")

    # OVERRIDES choose_action
    def choose_action(self, game_state: GameState, action_mask=None) -> Action:
        # Choose an action based on the current game state.
        # Game state is defined here:
        # https://github.com/lil-lab/cb2/blob/main/src/cb2game/pyclient/game_endpoint.py#L88

        # Agent creation tutorial here:
        # https://github.com/lil-lab/cb2/wiki/Cb2-Agents
        raise NotImplementedError("Implement this...")
"""


def generate_agent_boilerplate(agent_name: str = None):
    if agent_name is None:
        agent_name = StringFromUserInput(
            "Enter the name of your agent: ", default="MyAgent"
        )

    # Convert the agent name from CamelCase to snake_case.
    module_name = "".join(
        [c if c.islower() else "_" + c.lower() for c in agent_name]
    ).lstrip("_")

    # Create the agent code from the template.
    agent_code = AGENT_TEMPLATE.format(agent_name=agent_name, module_name=module_name)

    # If the file already exists, move it to agent_name_1.py, agent_name_2.py, etc.
    MoveFilesOutOfTheWay(f"{module_name}.py")
    with open(f"{module_name}.py", "w") as f:
        f.write(agent_code)
    slow_type(f"Created file {module_name}.py")

    slow_type(
        f"Boilerplate for {agent_name} created at {os.path.join(os.getcwd(), f'{agent_name.lower()}.py')}"
    )
    slow_type(
        f"You can generate configuration for your agent via `python3 -m cb2game.agents.generate_config {module_name}`"
    )
    slow_type("Please edit the file to implement your agent.")
    time.sleep(2)


if __name__ == "__main__":
    fire.Fire(generate_agent_boilerplate)
