Cereal Bar V2
=============

- [Cereal Bar V2](#cereal-bar-v2)
  - [Intro](#intro)
  - [Setup](#setup)
    - [Cloning the repository.](#cloning-the-repository)
    - [Download Submodules](#download-submodules)
    - [Python Dependencies](#python-dependencies)
    - [Pre-commit hooks.](#pre-commit-hooks)
    - [Server](#server)
    - [Client](#client)
    - [Deploying the server to a new machine.](#deploying-the-server-to-a-new-machine)
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

Setup
-----

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

### Python Dependencies

CB2 requires `Python 3.9` or higher.

We recommend you setup a virtual environment for the python dependencies. Here's a quick intro:

* Create the venv with: `python3 -m venv <env_name>` (run once).
* Enter the venv with: `source <env_name>/bin/activate`
* Now that you're in a virtual python environment, you can proceed below to install the server requirements & run the server.

Dependencies can be installed with:

```python3 -m pip install -r requirements.txt```

### Pre-commit hooks.

Precommit hooks are only required if you plan to contribute code to the
repository.  Otherwise, we recommend you skip this section.

Our precommit hooks require `python3.10` and `rustc` in order to run. Rust is
only used the first time to build a local binary of the typos tool, which
safeguards our repository from common typos developers make. You can download
python3.10 from python.org. You don't need it to be the python version used in
your venv or conda environment, it simply needs to be installed somewhere on
your system, and downloading the binary from python.org shouldn't interfere with
any existing installations. It will just make `python3.10` available as a binary
on the path. You can install rust from `https://www.rust-lang.org/tools/install`

Pre-commits take a long time (1-2m) to run the first time you commit, but they
should be fast (3-4 seconds) after that.

Install pre-commit hooks with

```pre-commit install```

If you don't have pre-commit already, you can get it by refreshing dependencies.

```python3 -m pip install -r requirements.txt```

On every commit, your commit will be blocked if any of the hooks defined in `.pre-commit-config.yaml` fail.

Hooks only run on files that you touch, so if you touch a new file with linter errors, you may inherit some legacy linter rrors. Don't have the time? Need to just commit? Try `git commit --no-verify`.

### Server

Launch the server on your desktop with:

```
python3 -m server.main --config_filepath="server/config/local-config.yaml"
```

To launch the server on a deployment machine, you'll want to use the SystemD
daemon. This can be installed with the `deploy/deploy.sh` script. It makes use
of the special config file `server/config/server-config.yaml`.

When you're done, you can quit the python venv with `deactivate` on the command line.

### Client

The client is a Unity project developed using Unity `Version 2020.3.xx`. This is contained in the `game/` directory. Once unity is installed, the application should open successfully.

For development purposes, the server may be run locally and the client run directly in the Unity editor. This connects to the server using the default lobby. For deployment, the game is compiled to HTML + WebGL.

The WebGL client can either be compiled from within Unity or from the command line with [build_client.sh](https://github.com/lil-lab/cb2/blob/main/build_client.sh). This launches a headless version of Unity which builds a WebGL client and moves it to the appropriate directory (`server/www/WebGL`) in the server.

```
# Before running this script, open it and change the UNITY variable to the path to your Unity executable.
./build_client.sh # Unity must be closed before running this.
```

This launches a headless version of Unity which builds a WebGL client and moves it to the appropriate directory (`server/www/WebGL`) in the server. Any pre-existing contents of `server/www/WebGL` are moved to `server/www/OLD_WebGL`.

Upon completion of this command, one may launch the server and access the client via ```localhost:8080/WebGL/index.html```.

### Deploying the server to a new machine.

The script `deploy/deploy.sh` should take care of everything. This installs a
SystemD Daemon which handles the CB2 server. See `deploy/systemd/README.md` for
more.

### Client API.

This repository contains a client API for writing agents which can interact with CB2. The client API is contained in directory `py_client/`, which contains a README with further information.

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
the schema of the `Scenario` dataclass defined in `server/messages/scenario.py`.

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
python3 -m server.map_tools.map_editor
```

No further command line parameters are needed. The editor will pop-up a GUI
asking you for a scenario file. We recommend starting with the template map, a
10x10 environment included in this repository at
`server/map_tools/maps/template.json`.

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
