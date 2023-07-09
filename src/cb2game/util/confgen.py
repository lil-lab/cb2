import os
import random
import readline  # Wraps input() to support backspace & left/right arrow navigation.
import sys
import time
from typing import List, Tuple


def slow_type(t, typing_speed=1000):
    """Prints text slowly, as if someone is typing it.
    Args:
        t: Text to print.
        typing_speed: Speed to type at. Characters per min.
    """
    for l in t:
        sys.stdout.write(l)
        sys.stdout.flush()
        time.sleep(random.random() * 10 / (typing_speed))
    print("")


def StringFromUserInput(prompt: str, default: str) -> int:
    """Prompts the user for a string."""
    prompt_string = f"{prompt} (default: {default}): "
    return input(prompt_string) or default


def IntegerFromUserInput(prompt: str, default: int) -> int:
    """Prompts the user for an integer."""
    while True:
        try:
            prompt_string = f"{prompt} (default: {default}): "
            return int(input(prompt_string) or str(default))
        except ValueError:
            slow_type("Invalid input. Try again, numbers only.")


def SelectionFromUserInput(
    prompt: str, options: List[str], default: str = None
) -> bool:
    """Prompts the user for a boolean. Accepts "y" or "n".

    Options are case insensitive. Preferably short or single-letter chars since the user needs to type them.

    If default is not None, accepts the empty string as a valid input. Default
    option will be capitalized when presented to the user.
    """
    # Make options all lowercase.
    options = [o.lower() for o in options]
    default = default.lower()

    if default is not None:
        assert (
            default in options
        ), "User input script error: default not in options. Please report this bug: https://github.com/lil-lab/cb2/issues"
    default_capitalized = [
        opt.upper() if opt == default else opt.lower() for opt in options
    ]
    options_string = "/".join(default_capitalized)

    while True:
        prompt_str = f"{prompt} ({options_string}) "
        ans = input(prompt_str)
        if ans.lower() in options:
            return ans
        if default and ans == "":
            return default


def BooleanFromUserInput(prompt: str, default: bool = None) -> bool:
    """Prompts the user for a boolean. Accepts "y" or "n".

    If default is not None, accepts the empty string as a valid input.
    """
    return SelectionFromUserInput(prompt, ["y", "n"], "y" if default else "n") == "y"


def TupleIntsFromUserInput(prompt: str, default: Tuple[int, int]) -> Tuple[int, int]:
    """Prompts the user for a tuple of integers."""
    while True:
        try:
            prompt_str = f"{prompt} ({', '.join([str(i) for i in default])}) "
            ans = input(prompt_str)
            if ans == "":
                return default
            result_tuple = tuple([int(i) for i in ans.split(",")])
            if len(result_tuple) != len(default):
                raise ValueError()
            return result_tuple
        except ValueError:
            slow_type("Invalid input. Try again, numbers only.")


def MoveFilesOutOfTheWay(filename: str = "") -> bool:
    """Moves the given file out of the way, if it exists.

    Returns True if the file was moved, False if it didn't exist.
    """
    if filename == "":
        return False

    filename_prefix = filename
    if filename.endswith(".py"):
        filename_prefix = filename[:-3]

    # If the file already exists, move it to agent_name_1.py, agent_name_2.py, etc.
    i = 1
    alt_name = filename_prefix
    while os.path.exists(f"{alt_name}.py"):
        alt_name = f"{filename_prefix}_{i}"
        i += 1

    if alt_name != filename_prefix:
        slow_type(
            f"File {filename_prefix}.py exists. Renaming to {alt_name}.py...",
            typing_speed=500,
        )
        slow_type(f"> mv {filename_prefix}.py {alt_name}.py", typing_speed=500)
        slow_type(f"Ctrl + C to cancel... (you have 3 seconds))", typing_speed=500)
        time.sleep(3)
        os.rename(f"{filename_prefix}.py", f"{alt_name}.py")
        slow_type(f"Moved {filename_prefix}.py to {alt_name}.py.")
        return True
    return False
