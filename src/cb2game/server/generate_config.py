"""Command line utility to create a default server config file."""
import hashlib
import os
import random
import sys
import time
from enum import Enum
from typing import List, Tuple

import fire
import yaml

from cb2game.server.config.config import Config
from cb2game.server.config.map_config import MapConfig

typing_speed = 700  # cpm


def slow_type(t):
    for l in t:
        sys.stdout.write(l)
        sys.stdout.flush()
        time.sleep(random.random() * 10 / (typing_speed))
    print("")


def IntegerFromUserInput(prompt: str, default: int) -> int:
    """Prompts the user for an integer."""
    while True:
        try:
            return int(input(prompt) or str(default))
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
        user_input = input(prompt_str)
        if user_input.lower() in options:
            return user_input
        if default and user_input == "":
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
            prompt_str = f"{prompt} ({default[0]}, {default[1]}) "
            user_input = input(prompt_str)
            if user_input == "":
                return default
            return tuple([int(i) for i in user_input.split(",")])
        except ValueError:
            slow_type("Invalid input. Try again, numbers only.")


def MapConfigFromUserInput() -> MapConfig:
    PrintSectionHeader(Section.MAPGEN_SETTINGS)
    slow_type(
        "Mapgen is the process of generating a map from a set of parameters and the random number generator."
    )
    config = MapConfig()

    # First, ask if the user just wants to use CB2 defaults. If so, return the default config.
    slow_type(
        "Configuring mapgen requires decided on about ~10 parameters, and is pretty open-ended. This can take a while. You can always do it yourself later by editing the config file."
    )
    slow_type("If you just want the defaults, you can skip all this.")
    use_defaults = BooleanFromUserInput("Use default mapgen settings?", default=True)
    if use_defaults:
        return config

    # Next, fill out the MapConfig dataclass.
    config.map_width, config.map_height = TupleIntsFromUserInput(
        "Map size (width, height): ", (config.map_width, config.map_height)
    )
    config.number_of_mountains_range = TupleIntsFromUserInput(
        "Number of mountains (min, max): ", config.number_of_mountains_range
    )
    config.number_of_cities_range = TupleIntsFromUserInput(
        "Number of cities (min, max): ", config.number_of_cities_range
    )
    config.number_of_lakes_range = TupleIntsFromUserInput(
        "Number of lakes (min, max): ", config.number_of_lakes_range
    )
    config.number_of_outposts_range = TupleIntsFromUserInput(
        "Number of outposts (min, max): ", config.number_of_outposts_range
    )

    slow_type(
        f"CB2 uses path routing to draw paths on the ground between features on the map. The path connection distance is the maximum distance that two objects can be and still have paths routed between them."
    )
    config.path_connection_distance = IntegerFromUserInput(
        "Path connection distance: ", config.path_connection_distance
    )

    return config


class Section(Enum):
    HTTP_SETTINGS = 0
    DATABASE_SETTINGS = 1
    GAME_SETTINGS = 2
    MAPGEN_SETTINGS = 3
    LOBBY_SETTINGS = 4
    CLIENT_SETTINGS = 5
    AUTH_SETTINGS = 6
    FINAL_SETTINGS = 7
    MAX = 8

    def to_str(self) -> str:
        return self.name.replace("_", " ").title()


def PrintSectionHeader(section: Section):
    """Prints a section header to the console."""
    slow_type(f"\n{section.to_str()} ({section.value + 1}/{Section.MAX.value})")
    slow_type("=" * len(section.to_str()))


def ConfigFromUserInput() -> Config:
    """Asks the user for input to create a Config object."""
    config = Config()

    PrintSectionHeader(Section.HTTP_SETTINGS)

    # First, ask for the server port. Default to 8080.
    config.port = IntegerFromUserInput("Server port: (default: 8080) ", 8080)

    PrintSectionHeader(Section.DATABASE_SETTINGS)
    # Next, ask for the database location. Default to "" -- Looks up system default via appdirs.
    slow_type(f"Default database location: {config.data_directory()}")
    slow_type(
        f"If you forget, you can always see the DB location later via `python3 -m cb2game.server.db_location`"
    )
    while True:
        db_path = input("Database location override: (default: '') ") or ""
        # If the db_path ends in "/", remove it.
        if db_path.endswith("/"):
            db_path = db_path[:-1]
        # Check if the DB path exists and is a directory.
        if os.path.isdir(db_path):
            config.data_prefix = db_path
            break
        if db_path == "":
            break
        # If the path is a file, clarify that the directory should be provided.
        if os.path.isfile(db_path):
            parent_dir = os.path.dirname(db_path)
            slow_type(
                f"Database path {db_path} is a file. The DB location must be a directory."
            )
            usedir = BooleanFromUserInput(f"Use {parent_dir} instead?", default=True)
            if usedir.lower() == "y":
                config.data_prefix = parent_dir
                break

    # Set the backup_db name to "game_backup.db.bk" by default.
    config.backup_db_path_suffix = "game_backup.db.bk"

    PrintSectionHeader(Section.GAME_SETTINGS)

    # How big should the pregenerated map cache be? Default to 50.
    slow_type(
        "Generating maps can take ~100ms of CPU time. As an optimization, the server will pre-generate a pool of maps while no games are in progress."
    )
    slow_type(
        "On a local dev machine, you'll want this to be small since you won't be running many games at once. On a production server, you'll want to find the right balance between memory consumption and map generation time."
    )
    slow_type("Set to zero to disable pregeneration.")
    config.map_cache_size = IntegerFromUserInput(
        "Pregenerated map pool size: (default: 50) ", 50
    )

    # Fog has two parameters: fog_start and fog_end. Fog_start is how many cells away things begin to get foggy. Fog_thickness is how many cells thick the fog is, and fog_end is fog_start + fog_thickness.
    slow_type(
        "Fog is a visual effect that makes the map harder to see as you get further away from objects. Only the follower sees fog."
    )
    slow_type(
        "Fog start is how many cells away things begin to get foggy. Fog end is how many cells away things are completely obscured."
    )
    config.fog_start = IntegerFromUserInput("Fog start: (default: 13) ", 13)
    config.fog_end = IntegerFromUserInput("Fog end: (default: 20) ", 20)

    # Mapgen configuration.
    MapConfigFromUserInput()

    PrintSectionHeader(Section.LOBBY_SETTINGS)
    slow_type(
        "Populating lobbies with default lobby set. You can change this later by editing the config file."
    )
    time.sleep(1)

    PrintSectionHeader(Section.CLIENT_SETTINGS)
    # Let's talk about uploading client exceptions.
    slow_type(
        "Any exceptions that occur in the unity client are uploaded to the server. This helps us debug issues. You can place a maximum limit on the number of exceptions that are stored in the database (highly recommended)."
    )
    slow_type(
        "This can take up space, recommend making it the default of 100 to start."
    )
    slow_type(
        "Client exceptions are stored in memory until they are committed to DB once all existing games are over, or on server close."
    )
    config.max_client_exceptions = IntegerFromUserInput(
        "Max client exceptions to store: (default: 100) ", 100
    )

    slow_type(
        f"Best to leave FPS option default. Some low-end laptops may perform better if a low FPS limit is set instead of self-managing (say, 30)"
    )
    config.fps_limit = IntegerFromUserInput(
        "Browser FPS limit: (-1 means let the browser optimize -- default).", -1
    )

    PrintSectionHeader(Section.AUTH_SETTINGS)
    slow_type(
        "Do you want to support Google Auth? You'll need to set up a Google Cloud project and OAuth credentials..."
    )
    google_auth = BooleanFromUserInput("Enable Google Auth?", default=False)
    if google_auth:
        slow_type(
            "Go here and create an OAuth client ID for a Web Application (very fast): https://console.cloud.google.com/apis/credentials/oauthclient"
        )
        slow_type("Then paste the client ID here...")
        config.google_oauth_client_id = input("Google OAuth Client ID: ") or ""

    slow_type(
        "Some server URLs are password-protected. See here for more info: https://github.com/lil-lab/cb2/wiki/Cb2-Url-Endpoints"
    )
    server_password = input("Server password (leave blank for no password): ") or ""
    if server_password != "":
        config.server_password_sha512 = hashlib.sha512(
            server_password.encode("utf-8")
        ).hexdigest()

    PrintSectionHeader(Section.FINAL_SETTINGS)
    slow_type(
        "Let's name your config. Full name will be <nameprefix>-<timestamp>-autoconf"
    )
    name = input("Config name prefix: (default: 'noname') ") or "noname"
    config.name = f"{name}-{int(time.time())}-autoconf"

    while True:
        config.comment = input(
            "Write a comment for this config (explain in a few words what this config is for and where it will be deployed): "
        )
        if config.comment != "":
            break
        slow_type(
            "Please provide a comment -- Remember, this is for your own benefit. You'll likely have many configs in the future."
        )
    return config


def main(all_defaults: bool = False):
    config = None
    if all_defaults:
        config = Config()
        config.name = "default"
        config.comment = "Default config"
    else:
        config = ConfigFromUserInput()
    # Use yaml to save this to a file.
    config_name = config.name + ".yaml"
    with open(config_name, "w") as f:
        yaml.dump(config, f)


if __name__ == "__main__":
    fire.Fire(main)
