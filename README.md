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
  - [Deploying a WebGL Client](#deploying-a-webgl-client)
  - [Server Endpoints](#server-endpoints)
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

We recommend you setup a virtual environment for the python dependencies. Here's a quick intro:

* Create the venv with: `python3 -m venv <env_name>` (run once).
* Enter the venv with: `source <env_name>/bin/activate`
* Now that you're in a virtual python environment, you can proceed below to install the server requirements & run the server.

Dependencies can be installed with:

```python3 -m pip install -r requirements.txt```

### Pre-commit hooks.

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

The client is a Unity project developed using Unity `Version 2020.3.25f1`. This is contained in the `game/` directory. No setup should be necessary, just open the project in Unity.

### Deploying the server to a new machine.

The script `deploy/deploy.sh` should take care of everything. This installs a
SystemD Daemon which handles the CB2 server. See `deploy/systemd/README.md` for
more.

### Client API.

This repository contains a client API for writing agents which can interact with CB2. The client API is contained in directory `py_client/`, which contains a README with further information.

Deploying a WebGL Client
------------------------

For development purposes, the server may be run locally and the client run directly in the Unity editor. For deployment, the game is compiled to Web Assembly and WebGL is used for efficient graphics in the browser. You can deploy a new version of the client by running:

```
./build_client.sh # Unity must be closed when running this.
```

This launches a headless version of Unity which builds a WebGL client and moves it to the appropriate directory (`server/www/WebGL`) in the server.

Upon completion of this command, one may launch the server and access the client via ```0.0.0.0:8080/WebGL/index.html```. The old build of the client is preserved at  `server/www/OLD_WebGL`.

[0]: https://github.com/lil-lab/cerealbar
[1]: https://git-lfs.github.com

Server Endpoints
----------------

| Endpoint URL         | Description                                           |
| -------------------- | ----------------------------------------------------- |
| `/`                  | Serves static files from `server/www`.                |
| `/status`            | Prints server status in JSON.                         |
| `/player_endpoint`   | Websocket endpoint for communication with clients.    |
| `/assets/{asset_id}` | Currently unused mechanism to obscurely serve assets. |

Resources
---------

`resources.txt`: Links to resources that were useful in development of this game.

`guidelines.txt`: Guiding thoughts on style, code review, and source code management. Always up for generous interpretation and change.
