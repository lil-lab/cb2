import dataclasses
import importlib
import inspect
import os
import time

import fire
import yaml

from cb2game.agents.agent import Agent
from cb2game.util.confgen import (
    BooleanFromUserInput,
    IntegerFromUserInput,
    StringFromUserInput,
    TupleIntsFromUserInput,
    slow_type,
)


def get_input_for_type(typ):
    if typ == int:
        return IntegerFromUserInput
    elif typ == str:
        return StringFromUserInput
    elif typ == bool:
        return BooleanFromUserInput
    elif typ == tuple:
        return TupleIntsFromUserInput
    else:
        # Return None. The parent class will use the default value.
        return None


def configure_agent(agent_module_name: str, all_defaults: bool = False):
    agent_module = importlib.import_module(agent_module_name)

    # Search for Agent class in the module
    agent_class = None
    for name in dir(agent_module):
        obj = getattr(agent_module, name)
        if isinstance(obj, type) and issubclass(obj, Agent) and obj is not Agent:
            # Confirm that the class is in the same file as the module.
            if obj.__module__ != agent_module_name:
                continue
            agent_class = obj
            break

    if not agent_class:
        raise Exception("Could not find Agent class in the provided module")

    # Print the discovered agent class name.
    slow_type(f"Creating config for agent class: {agent_class.__name__}")

    # Extract the config class from the first argument type hint of the Agent's constructor
    signature = inspect.signature(agent_class.__init__)
    if "config" not in signature.parameters:
        raise Exception("Agent's constructor doesn't have a 'config' parameter")

    config_class = signature.parameters["config"].annotation
    if config_class == inspect._empty:
        raise Exception(
            "Agent's constructor doesn't have a type hint for the 'config' parameter"
        )

    # Initialize an empty dictionary to hold the field values.
    field_values = {}

    # Get a list of the fields in the dataclass.
    fields = dataclasses.fields(config_class)

    # Iterate over each field, getting user input.
    if all_defaults:
        for field in fields:
            field_values[field.name] = field.default
    else:
        for field in fields:
            # Get input function for this field's type
            input_function = get_input_for_type(field.type)
            # Get default value for this field
            default_value = (
                field.default if field.default != dataclasses.MISSING else None
            )
            # Use input function to get value for this field from user
            field_values[field.name] = input_function(
                f"Enter {field.name}", default_value
            )

    # Construct the agent configuration dictionary.
    agent_config = {
        "my_agent": {
            "type": f"{agent_module_name}.{agent_class.__name__}",
            "config": field_values,
        }
    }

    # First, we convert the class name to snake case.
    # Determine the filename based on the agent class name.
    # If the filename already exists, rename the old file to {class_name}_1.yaml, {class_name}_2.yaml, etc.
    # Then save the new config to {class_name}.yaml.
    class_name_snake_case = "".join(
        ["_" + c.lower() if c.isupper() else c for c in agent_class.__name__]
    ).lstrip("_")
    filename = f"{class_name_snake_case}.yaml"
    first_filename = filename
    i = 1
    while os.path.exists(filename):
        filename = f"{class_name_snake_case}_{i}.yaml"
        i += 1

    # Write the dictionary to a YAML file.
    slow_type(f"Writing config to {first_filename}...")
    if filename != first_filename:
        slow_type(
            f"This file already exists. Renaming old file {first_filename} to {filename}..."
        )
        slow_type(f"> mv {first_filename} {filename}")
        time.sleep(2)
        os.rename(first_filename, filename)
    with open(first_filename, "w") as f:
        yaml.dump(agent_config, f, sort_keys=False)
    slow_type(f"Saved config to {first_filename}...")


if __name__ == "__main__":
    # Usage: python script.py module.name
    fire.Fire(configure_agent)
