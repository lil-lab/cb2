"""Command line utility to create a default server config file."""
import hashlib
import os
import readline  # Wraps input() to support backspace & left/right arrow navigation.
import time
from enum import Enum

import fire
import yaml

from cb2game.server.config.config import Config
from cb2game.server.config.map_config import MapConfig
from cb2game.server.lobby_consts import LobbyInfo, LobbyType
from cb2game.util.confgen import (
    BooleanFromUserInput,
    IntegerFromUserInput,
    TupleIntsFromUserInput,
    slow_type,
)


class Section(Enum):
    HTTP_SETTINGS = 0
    DATABASE_SETTINGS = 1
    GAME_SETTINGS = 2
    MAPGEN_SETTINGS = 3
    CLIENT_SETTINGS = 4
    AUTH_SETTINGS = 5
    LOBBY_SETTINGS = 6
    FINAL_SETTINGS = 7
    MAX = 8

    def to_str(self) -> str:
        return self.name.replace("_", " ").title()


def PrintSectionHeader(section: Section):
    """Prints a section header to the console."""
    slow_type(f"\n{section.to_str()} ({section.value + 1}/{Section.MAX.value})")
    slow_type("=" * len(section.to_str()))


def FindOrCreateDefaultLobby(config: Config) -> LobbyInfo:
    """Finds or creates a default lobby. Lobbies are saved in a list."""
    default_lobbies = [x for x in config.lobbies if x.name == "default"]
    if len(default_lobbies) == 0:
        default_lobby = LobbyInfo(
            "default",
            LobbyType.OPEN,
            "Default lobby for testing.",
            40,
            1,
            False,
        )
        config.lobbies.append(default_lobby)
        return default_lobby
    else:
        return default_lobbies[0]


def MapConfigFromUserInput() -> MapConfig:
    PrintSectionHeader(Section.MAPGEN_SETTINGS)
    slow_type(
        "Mapgen is the process of generating a map from a set of parameters and the random number generator."
    )
    default = MapConfig()

    # First, ask if the user just wants to use CB2 defaults. If so, return the default config.
    slow_type(
        "Configuring mapgen requires decided on about ~10 parameters, and is pretty open-ended. This can take a while. You can always do it yourself later by editing the config file."
    )
    slow_type("If you just want the defaults, you can skip all this.")
    use_defaults = BooleanFromUserInput("Use default mapgen settings?", default=True)
    if use_defaults:
        return default

    # Next, fill out the MapConfig dataclass.
    map_width, map_height = TupleIntsFromUserInput(
        "Map size (width, height): ", (default.map_width, default.map_height)
    )
    number_of_mountains_range = TupleIntsFromUserInput(
        "Number of mountains (min, max): ", default.number_of_mountains_range
    )
    number_of_cities_range = TupleIntsFromUserInput(
        "Number of cities (min, max): ", default.number_of_cities_range
    )
    number_of_lakes_range = TupleIntsFromUserInput(
        "Number of lakes (min, max): ", default.number_of_lakes_range
    )
    number_of_outposts_range = TupleIntsFromUserInput(
        "Number of outposts (min, max): ", default.number_of_outposts_range
    )

    slow_type(
        f"CB2 uses path routing to draw paths on the ground between features on the map. The path connection distance is the maximum distance that two objects can be and still have paths routed between them."
    )
    path_connection_distance = IntegerFromUserInput(
        "Path connection distance: ", default.path_connection_distance
    )

    return MapConfig(
        map_width=map_width,
        map_height=map_height,
        number_of_mountains_range=number_of_mountains_range,
        number_of_cities_range=number_of_cities_range,
        number_of_lakes_range=number_of_lakes_range,
        number_of_outposts_range=number_of_outposts_range,
        path_connection_distance=path_connection_distance,
    )


def ConfigFromUserInput() -> Config:
    """Asks the user for input to create a Config object."""
    config = Config()

    PrintSectionHeader(Section.HTTP_SETTINGS)

    # First, ask for the server port. Default to 8080.
    config.http_port = IntegerFromUserInput("Server port", 8080)

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
            if usedir:
                config.data_prefix = parent_dir
                break
        # If the path doesn't exist, re-prompt.
        slow_type(f"Database path {db_path} does not exist.")

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
    config.map_cache_size = IntegerFromUserInput("Pregenerated map pool size", 50)

    # Fog has two parameters: fog_start and fog_end. Fog_start is how many cells away things begin to get foggy. Fog_thickness is how many cells thick the fog is, and fog_end is fog_start + fog_thickness.
    slow_type(
        "Fog is a visual effect that makes the map harder to see as you get further away from objects. Only the follower sees fog."
    )
    slow_type(
        "fog_start is how many cells away things begin to get foggy. fog_end is how many cells away things are completely obscured."
    )
    config.fog_start = IntegerFromUserInput("Enter fog_start", 13)
    config.fog_end = IntegerFromUserInput("Enter fog_end", 20)

    # Mapgen configuration.
    config.map_config = MapConfigFromUserInput()

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
        "Max client exceptions to store", 100
    )

    slow_type(
        f"Best to leave FPS option default. Some low-end laptops may perform better if a low FPS limit is set instead of self-managing (say, 30). -1 means let the browser optimize for device settings."
    )
    config.fps_limit = IntegerFromUserInput("Browser FPS limit", -1)

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
    slow_type(
        "NOTE: Save your password. Passwords are stored in the config as an SHA512 hash. We don't store the password itself, and it's impossible to recover the password from the hash."
    )
    slow_type(
        "If you forget your password, you'll need to delete the hash in the config file and restart the server."
    )
    server_password = input("Server password (leave blank for no password): ") or ""
    if server_password != "":
        config.server_password_sha512 = hashlib.sha512(
            server_password.encode("utf-8")
        ).hexdigest()

    PrintSectionHeader(Section.LOBBY_SETTINGS)
    slow_type(
        "Populating lobbies with default lobby set. You can change this later by editing the config file."
    )
    # The default lobby is usually google authenticated. If we didn't enable
    # this in the previous step, we'll disable it here and make the default
    # lobby unauthenticated.
    if not google_auth:
        lobby = FindOrCreateDefaultLobby(config)
        lobby.type = LobbyType.OPEN
        lobby.comment += " (Google Oauth disabled, default lobby is unauthenticated.)"
        slow_type(
            "Since Google Oauth wasn't enabled, changing default lobby to not require Google authentication."
        )
        time.sleep(2)
    time.sleep(1)

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
        lobby = FindOrCreateDefaultLobby(config)
        lobby.type = LobbyType.OPEN
        lobby.comment += " (Google Oauth disabled, default lobby is unauthenticated.)"
        slow_type(
            "Since Google Oauth wasn't enabled (default), changing default lobby to not require Google authentication."
        )
        time.sleep(0.5)
    else:
        config = ConfigFromUserInput()
    # Use yaml to save this to a file.
    config_name = config.name + ".yaml"
    # If the file already exists, move it to a new name filename_1.yaml, etc.
    first_name = config_name
    i = 1
    while os.path.exists(config_name):
        config_name = config.name + f"_{i}.yaml"
        i += 1
    slow_type(f"Writing config to {first_name}")
    if first_name != config_name:
        slow_type(
            f"Config with name {first_name} already exists. Renaming it to {config_name}."
        )
        slow_type(f"> mv {first_name} {config_name}")
        time.sleep(2)
        os.rename(first_name, config_name)
    with open(first_name, "w") as f:
        yaml.dump(config, f, sort_keys=False)
    slow_type(f"Config saved to {first_name}.")
    time.sleep(0.5)


if __name__ == "__main__":
    fire.Fire(main)
