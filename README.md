Cereal Bar V2
=============

- [Cereal Bar V2](#cereal-bar-v2)
  - [Intro](#intro)
  - [Installation](#installation)
  - [Getting Started](#getting-started)
    - [Installing the Unity client.](#installing-the-unity-client)
    - [Creating a config.](#creating-a-config)
    - [Running the server.](#running-the-server)
    - [Deploying the server to a new machine.](#deploying-the-server-to-a-new-machine)
  - [Development](#development)
    - [Cloning the repository.](#cloning-the-repository)
    - [Download Submodules](#download-submodules)
    - [Installing Dev Package.](#installing-dev-package)
    - [Pre-commit hooks.](#pre-commit-hooks)
    - [Server](#server)
    - [Client](#client)
    - [Client API.](#client-api)
    - [Scenario Rooms](#scenario-rooms)
      - [Creating a scenario.](#creating-a-scenario)
      - [Launching a scenario.](#launching-a-scenario)
      - [Scenario (Map) Editor](#scenario-map-editor)
        - [Requirements](#requirements)
        - [Running the map editor](#running-the-map-editor)
  - [Documentation](#documentation)
  - [Server Endpoints](#server-endpoints)
      - [Password-protected endpoints.](#password-protected-endpoints)
  - [Demonstration Model](#demonstration-model)
  - [Dataset](#dataset)
  - [Resources](#resources)

Intro
-----

Cereal Bar is a two-player web game designed for studying language
understanding agents in collaborative interactions. This repository contains
code for the game, a webapp hosting the game, and various related tools.

This is a remake of the original Cereal Bar, which can be found [here][0]

Installation
------------

The easiest way to install CB2 is via pip. You can install the game with:

```
python3 -m pip install cb2game
```

Getting Started
---------------

### Installing the Unity client.

You'll need to get a version of the front-end unity client, as this doesn't come with the pip package. You can fetch the latest client released on Github via:

```
python3 -m cb2game.server.fetch_client
```

### Creating a config.

The server requires a config file to run. We provide a config generator script
that walks you through the step of setting up the configuration for your server.
You can run it with:

```
python3 -m cb2game.server.generate_config
```

This will create a config file in the current directory. If you just want a
default config, you can just run:

```
python3 -m cb2game.server.generate_config --all_defaults
```

Which will create `default.yaml` in the current directory.

### Running the server.

Once you have a config, you can run the server with:

```
python3 -m cb2game.server.main --config_filepath <path_to_config>
```

You can now access the game instance at `http://localhost:8080/`

### Deploying the server to a new machine.

If you're setting up a web server, you'll want to run CB2 as a daemon. This
provides a few benefits:
- The server will automatically restart if it crashes.
- Logs will be automatically rotated.
- You can start/stop the server with `systemctl`.
- The server will run in the background, and you can log out of the machine without stopping the server.

We provide a script for deploying CB2 as a systemd service on Ubuntu 22.04 LTS:

```
# Install cb2game service.
python3 -m cb2game.deploy install <path-to-config.yaml>

# Fetch cb2game front-end client and install it. Uses latest release on Github
# if no locally built client is specified. Unless you're interested in
# customizing CB2's Unity client, you should leave this blank.
python3 -m cb2game.deploy fetch-client <optional-path-to-local-client>

# Start the service (check localhost:8080 or python -m cb2game.deploy logs to
# verify)
python3 -m cb2game.deploy start

# Check localhost:8080/ in your browser. The server should now be started!
```

Here's some other useful commands:
```
# Update the current cb2game version. Latest if no version specified.
python3 -m cb2game.deploy update-to-version <optional-version>

# See where all files are installed, current cb2game version installed on system.
python3 -m cb2game.deploy info

# Update the config used by the service.
python3 -m cg2game.deploy update_config <path-to-config.yaml>

# Possibly diagnose system issues causing install to fail.
python3 -m cb2game.deploy diagnose

# Restart
python3 -m cb2game.deploy restart

# Stop the service
python3 -m cb2game.deploy stop

# Access service logs.
python3 -m cb2game.deploy logs

# Uninstall.
python3 -m cb2game.deploy uninstall
```


Development
-----------

Here's the instructions if you'd like to setup CB2 for development. This
installs the `cb2game` package in editable mode, so you can make changes to the
code and have them reflected in the server without having to reinstall the
package.

### Cloning the repository.

This repository uses [git-lfs][1]. Event though newer versions of git (>=
2.3.0) can handle this automatically, the .gitattributes file falls back to
git-lfs for all binary files by default. git lfs is required, so make sure to
install and use `git lfs clone` to clone this repository.

### Download Submodules

This repository contains submodules. As such, you need to run this step to
fetch submodules after cloning:

```
cd repo
git submodule init
git submodule update
```

### Installing Dev Package.

CB2 requires `Python 3.9` or higher.

We recommend you setup a virtual environment for the development of CB2. You can do this with:

* Create the venv with: `python3 -m venv <env_name>` (run once).
* Enter the venv with: `source <env_name>/bin/activate`
* Now that you're in a virtual python environment, you can proceed below to install the server in dev mode.

Install the server in editable mode with:

```
# Run from the root of the repo.
python3 -m pip install -e .
```

### Pre-commit hooks.

Precommit hooks are only required if you plan to contribute code to the
repository.  But they're highly recommended, as they'll run formatting tools on
your code before you commit it, and block the commit if there are any failing
unit tests.  If a unit test fails, it means you have broken something, and you
shouldn't be committing it.

Some precommit hooks may require `python3.10` in order to run. You can download
python3.10 from python.org. You don't need it to be the python version used in
your venv or conda environment, or even the system default. It simply needs to
be installed somewhere on your system, and downloading the binary from
python.org shouldn't interfere with any existing python environments. It will just
make `python3.10` available as a binary on the path.

Pre-commits take a long time (1-2m) to run the first time you commit, but they
should be fast (3-4 seconds) after that.

Install pre-commit hooks with

```pre-commit install```

If you don't have pre-commit already, you can get it by refreshing dependencies.

On every commit, your commit will be blocked if any of the hooks defined in `.pre-commit-config.yaml` fail.

### Server

Launch the server on your desktop with:

```
python3 -m cb2game.server.main --config_filepath <path-to-config>
```

To launch the server on a deployment machine, you'll want to use the SystemD
daemon. This can be installed with the `deploy/deploy.sh` script. It makes use
of the special config file `server/config/server-config.yaml`.

When you're done, you can quit the python venv with `deactivate` on the command line.

### Client

CB2 is designed such that most game logic can be modified without having to
recompile the Unity client. However, if you do need to recompile the client,
you'll need to install Unity.

The client is a Unity project developed using Unity `Version 2020.3.xx`. This is contained in the `unity_client/` directory. Once unity is installed, the application should open successfully.

For development purposes, the server may be run locally and the client run directly in the Unity editor. This connects to the server using the default lobby. For deployment, the game is compiled to HTML + WebGL.

The WebGL client can either be compiled from within Unity or from the command line with [build_client.sh](https://github.com/lil-lab/cb2/blob/main/build_client.sh). This launches a headless version of Unity which builds a WebGL client and moves it to the appropriate directory (`server/www/WebGL`) in the server.

```
# Before running this script, open it and change the UNITY variable to the path to your Unity executable.
./build_client.sh # Unity must be closed before running this.
```

This launches a headless version of Unity which builds a WebGL client and moves it to the appropriate directory (`server/www/WebGL`) in the server. Any pre-existing contents of `server/www/WebGL` are moved to `server/www/OLD_WebGL`.

Upon completion of this command, one may launch the server and access the client via ```localhost:8080/play```.

If you built the client from unity and want to install it, you can run:

```
python3 -m cb2game.server.fetch_client ----local_client_path <path_to_WebGL_dir>
```

### Client API.

This repository contains a client API for writing agents which can interact with CB2. The client API is contained in directory `pyclient/`, which contains a README with further information.

### Scenario Rooms
CB2 contains a scenario room to allow for research that wants to investigate
custom scenarios in a controlled manner. Scenario rooms are single player
(follower role only, currently), and allow for a script to attach via the Python
API and monitor the game state. The script can at any time load a new map, or
send instructions/feedback just as the leader would. We provide an in-game UI to
turn an existing game into a scenario for later inspection.

#### Creating a scenario.
You can create a scenario from inside of a game by hitting escape and then "Save
Scenario State". You must be in the `open` lobby to do this.

Access the open lobby via endpoint `/play?lobby_name=open`.

The scenario file itself is a JSON file that you can download. The JSON follows
the schema of the `Scenario` dataclass defined in `src/cb2game/server/messages/scenario.py`.

Scenarios are currently follower-only. If it wasn't the followers turn when you
created the scenario, then the follower will be unable to move. Make sure to
edit the scenario file, specifically the `turn` field of the `turn_state` entry,
to equal to the value `1` (follower). You may also want to give the follower a
large number of moves, so that they can move freely about the scenario.

#### Launching a scenario.
You can launch a scenario by entering a room in the scenario lobby. Scenario
rooms are 1 player, and you play as the follower.

Access the scenario lobby via endpoint `/play?lobby_name=scenario-lobby`

Then hit "Join Game". You'll immediately join an empty scenario. Load a scenario
file by hitting esc and clicking on `Upload Scenario State`. If this item
doesn't appear in the escape menu, reload the page and retry (this sometimes happens).

The scenario should then load. If the file is invalid, then the server will end
the game immediately.

#### Scenario (Map) Editor

CB2 contains a map editor, which you can use to craft custom maps. These maps
can be explored in a custom scenario.

##### Requirements
The map editor requires that tkinter is installed on your system. If you didn't
do this prior to setting up your virtual environment, you'll need to install
tkinter, and then re-create your venv (should only take a few minutes --
deleting venv/ is a relatively safe operation)

OSX
```
brew install python-tk
```

Ubuntu
```
sudo apt-get install python-tk python3-tk tk-dev
```

##### Running the map editor

Launch the map editor with the command:

```
# Must be in python virtual env first!
python3 -m cb2game.server.map_tools.map_editor
```

No further command line parameters are needed. The editor will pop-up a GUI
asking you for a scenario file. We recommend starting with the template map, a
10x10 environment included in this repository at
`src/cb2game/server/map_tools/maps/template.json`.

Upon closing the editor, it pops up another GUI to save the
modified scenario -- Make sure to do this, or your changes will be lost. Hitting
Q or Escape will close the editor, so be careful!

There's currently no undo. If you made a change you want to undo, close the
editor without saving, and then reload the scenario file.

The green button in the UI is to save & quit.
The red button in the UI clears the screen and replaces all tiles with green
tiles.

You can resize a scenario map by editing the "rows" and "cols" fields respectively
of the scenario file with a text editor.

Documentation
-------------
For more information on CB2, see the [CB2 Wiki](https://github.com/lil-lab/cb2/wiki).

Server Endpoints
----------------

The CB2 server creates a number of HTTP endpoints for inspecting and accessing user data from a live server instance. This makes it easier to administer experiments with CB2 – server admins can inspect games in-progress live.

| Endpoint URL         | Description                                           |
| -------------------- | ----------------------------------------------------- |
| `/`                  | CB2 Homepage. Contains links to docs, code, etc.      |
| `/play`              | Serves Unity WebGL client                             |
| `/player_endpoint`   | Websocket endpoint for communication with clients.    |
| `/view/games`        | View all games played on the server.                  |

For a full list of endpoints and more info, see the [CB2 URLs doc](https://github.com/lil-lab/cb2/wiki/Cb2-Url-Endpoints) in the wiki.

#### Password-protected endpoints.
The server contains some optionally password-protected endpoints. These are
endpoints which allow access to game data or live user information. You can set
the password in the config via the server_password_sha512 field. Do not put the
plaintext password in your configuration file. Instead, you use a sha512
hash of the password. You can generate a password hash with the following
command:

```
python3 -c 'import hashlib; print(hashlib.sha512(b"your_password").hexdigest())'
```

To access password-protected endpoints, you must pass the password as a query
parameter. For example, if your password is `password`, you would access the
`/view/games` endpoint with the following URL:

```
http://localhost:8080/view/games?password=password
```


Demonstration Model
-------------------

We trained and deployed a baseline demonstration model that is publicly
available online.  You can play against the model on our website, at
[cb2.ai/][2]. For more information on the model, including a link to download
the weights, see the readme at `follower_bots/README.md`.

Dataset
-------

We are releasing a dataset of 560 games collected on Amazon mechanical turk. These are in 3 sections:

```
185 human-human games used to train the demonstration model
187 human-human games collected deploying the demo model on AWS mech turk.
188 human-model games collected deploying the demo model on AWS mech turk.
```

The dataset is [available for download here][3]. For data format documentation,
see our well-documentated schema definition at server/schemas/event.py. JSON files
are serialized from the Sqlite database, and contain the same schema.

Resources
---------

`resources.txt`: Links to resources that were useful in development of this game.

`guidelines.txt`: Guiding thoughts on style, code review, and source code management. Always up for generous interpretation and change.


[0]: https://github.com/lil-lab/cerealbar
[1]: https://git-lfs.github.com
[2]: https://cb2.ai/
[3]: https://lil.nlp.cornell.edu/resources/cb2-base/cb2-base-data.tar.bz2
