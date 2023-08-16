#!/usr/bin/env python3

import os
import pathlib
import subprocess
import sys
import tempfile

from cb2game.util.confgen import slow_type

SERVICE_NAME = "cb2game.service"
SERVICE_PATH = "/etc/systemd/system/"
VENV_PATH = "/opt/cb2game_venv/"
CONFIG_DIR = "/etc/cb2game/"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.conf")
SERVICE_TEMPLATE = """
[Unit]
Description=CB2 Service
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
User={username}
ExecStart={venv_path}/bin/python -m cb2game.server.main --config_filepath {config_path}

[Install]
WantedBy=multi-user.target
"""


def sudo_run(
    command_list, user=None, check=True, input=None, encoding=None, stdout=None
):
    slow_type("Running command: {}".format(" ".join(command_list)))
    sudo_command_list = ["sudo"]
    if user:
        sudo_command_list.extend(["-u", user])
    sudo_command_list.extend(command_list)
    subprocess.run(
        sudo_command_list, check=check, input=input, encoding=encoding, stdout=stdout
    )


def write_service_file(content):
    with open("/tmp/{}".format(SERVICE_NAME), "w") as f:
        f.write(content)
    sudo_run(
        ["mv", "/tmp/{}".format(SERVICE_NAME), os.path.join(SERVICE_PATH, SERVICE_NAME)]
    )


def install(user_config_path):
    slow_type(
        "Installing cb2game service... If this fails, you can try python3 -m cb2game.deploy diagnose"
    )
    username = os.getlogin()

    # If the service is already installed, print an error and exit.
    if os.path.exists(os.path.join(SERVICE_PATH, SERVICE_NAME)):
        slow_type(
            "Service is already installed. Run python3 -m cb2game.deploy uninstall to uninstall."
        )
        sys.exit(1)

    # You can't copy a venv, so use pip freeze to clone it.
    slow_type("Cloning Virtualenv...")
    if os.path.exists(VENV_PATH):
        sudo_run(["rm", "-rf", VENV_PATH])

    # Create the venv.
    sudo_run(["python3", "-m", "venv", VENV_PATH])

    # Get the pip requirements for the current venv.
    pip_freeze = subprocess.run(
        [f"{sys.prefix}/bin/pip", "freeze"], stdout=subprocess.PIPE
    ).stdout.decode("utf-8")
    # Save to temp requirements.txt.
    with tempfile.NamedTemporaryFile(mode="w") as f:
        f.write(pip_freeze)
        f.flush()
        # Install the pip requirements into the new venv.
        sudo_run(
            [
                f"HOME={pathlib.Path.home()}",
                f"{VENV_PATH}/bin/python",
                "-m",
                "pip",
                "install",
                "--no-cache-dir",
                "-r",
                "{}".format(f.name),
            ]
        )

    if not os.path.exists(CONFIG_DIR):
        sudo_run(["mkdir", CONFIG_DIR])
    sudo_run(["cp", user_config_path, CONFIG_PATH])

    service_content = SERVICE_TEMPLATE.format(
        username=username, venv_path=VENV_PATH, config_path=CONFIG_PATH
    )

    write_service_file(service_content)

    sudo_run(["systemctl", "daemon-reload"])

    slow_type(
        "Installation complete. Run python3 -m cb2game.deploy fetch-client to fetch the front-end client. Then start the service with python3 -m cb2game.deploy start"
    )


def uninstall():
    # If the service is not installed, print an error and exit.
    if not os.path.exists(os.path.join(SERVICE_PATH, SERVICE_NAME)):
        slow_type(
            "Service is not installed. Install with python3 -m cb2game.deploy install <config>"
        )
        sys.exit(1)

    slow_type("Uninstalling cb2game service...")
    sudo_run(["systemctl", "stop", SERVICE_NAME])
    sudo_run(["systemctl", "disable", SERVICE_NAME])
    sudo_run(["rm", os.path.join(SERVICE_PATH, SERVICE_NAME)])
    sudo_run(["rm", "-rf", VENV_PATH])
    sudo_run(["rm", CONFIG_PATH])
    sudo_run(["rm", "-rf", CONFIG_DIR])
    sudo_run(["systemctl", "daemon-reload"])
    slow_type("Uninstallation complete.")


def update_config(user_config_path):
    slow_type("Updating cb2game configuration...")
    sudo_run(["cp", user_config_path, CONFIG_PATH])
    slow_type("Configuration updated.")
    # If the service is running, restart it. Hide output from this command.
    status_code = subprocess.run(
        ["systemctl", "is-active", SERVICE_NAME],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode
    if status_code == 0:
        slow_type("Config updated while service was running. Restarting service...")
        restart()


def start():
    if not os.path.exists(os.path.join(SERVICE_PATH, SERVICE_NAME)):
        slow_type(
            "Service is not installed. Install with python3 -m cb2game.deploy install <config>"
        )
        sys.exit(1)
    sudo_run(["systemctl", "start", SERVICE_NAME])


def stop():
    if not os.path.exists(os.path.join(SERVICE_PATH, SERVICE_NAME)):
        slow_type(
            "Service is not installed. Install with python3 -m cb2game.deploy install <config>"
        )
        sys.exit(1)
    sudo_run(["systemctl", "stop", SERVICE_NAME])


def restart():
    if not os.path.exists(os.path.join(SERVICE_PATH, SERVICE_NAME)):
        slow_type(
            "Service is not installed. Install with python3 -m cb2game.deploy install <config>"
        )
        sys.exit(1)
    sudo_run(["systemctl", "restart", SERVICE_NAME])


def status():
    if not os.path.exists(os.path.join(SERVICE_PATH, SERVICE_NAME)):
        slow_type(
            "Service is not installed. Install with python3 -m cb2game.deploy install <config>"
        )
        sys.exit(1)
    sudo_run(["systemctl", "status", SERVICE_NAME], check=False)


def logs():
    if not os.path.exists(os.path.join(SERVICE_PATH, SERVICE_NAME)):
        slow_type(
            "Service is not installed. Install with python3 -m cb2game.deploy install <config>"
        )
        sys.exit(1)
    sudo_run(["journalctl", "-u", SERVICE_NAME])


def update_to_version():
    version = sys.argv[2] if len(sys.argv) > 2 else "latest"

    if version == "latest":
        subprocess.run(
            [
                f"{VENV_PATH}/bin/pip",
                "install",
                "--no-cache-dir",
                "--upgrade",
                "cb2game",
            ],
            check=True,
        )
    else:
        subprocess.run(
            [
                f"{VENV_PATH}/bin/pip",
                "install",
                "--no-cache-dir",
                f"cb2game=={version}",
            ],
            check=True,
        )

    slow_type(f"Updated cb2game to version: {version}")
    restart()


def fetch_client(local_client_path: str = None):
    if not os.path.exists(os.path.join(SERVICE_PATH, SERVICE_NAME)):
        slow_type(
            "Service is not installed. Install with python3 -m cb2game.deploy install <config>"
        )
        sys.exit(1)
    slow_type("Fetching client...")
    if local_client_path:
        # Use cb2game.server.fetch_client to fetch the client.
        sudo_run(
            [
                f"{VENV_PATH}/bin/python",
                "-m",
                "cb2game.server.fetch_client",
                local_client_path,
            ],
            check=True,
        )
        return
    # Use cb2game.server.fetch_client to fetch the client.
    sudo_run(
        [f"{VENV_PATH}/bin/python", "-m", "cb2game.server.fetch_client"], check=True
    )


def info():
    # Check if the service is installed. If not, exit.
    if not os.path.exists(os.path.join(SERVICE_PATH, SERVICE_NAME)):
        slow_type("Service is not installed.")
        sys.exit(1)
    slow_type("Service name: {}".format(SERVICE_NAME))
    slow_type("Service path: {}".format(SERVICE_PATH))
    slow_type("Virtualenv path: {}".format(VENV_PATH))
    slow_type("Config path: {}".format(CONFIG_PATH))
    cb2game_version = (
        subprocess.run(
            [f"{VENV_PATH}/bin/python", "-m", "pip", "show", "cb2game"],
            check=True,
            stdout=subprocess.PIPE,
        )
        .stdout.decode("utf-8")
        .split("\n")[1]
        .split(":")[1]
        .strip()
    )
    slow_type("System cb2game version: {}".format(cb2game_version))


def diagnose():
    # Check Ubuntu version
    version_check = subprocess.run(
        ["lsb_release", "-rs"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    ubuntu_version = version_check.stdout.decode("utf-8").strip()

    if ubuntu_version != "22.04":
        slow_type(
            f"Warning: You are using Ubuntu {ubuntu_version}. This software is tested and optimized for Ubuntu 22.04 LTS. Any issues encountered on other versions will be up to the user to resolve."
        )
        return

    slow_type("No issues found. Ubuntu version {}".format(ubuntu_version))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        slow_type(
            "Please provide a command: install, uninstall, fetch-client, update-config, start, stop, restart, logs, update-to-version, info, diagnose."
        )
        sys.exit(1)

    command = sys.argv[1]
    if command == "install":
        if len(sys.argv) < 3:
            slow_type(
                "Please provide the path to the config file. You can generate it with python3 -m cb2game.server.generate_config"
            )
            sys.exit(1)
        install(sys.argv[2])
    elif command == "uninstall":
        uninstall()
    elif command == "update-config":
        if len(sys.argv) < 3:
            slow_type("Please provide the path to the new config file.")
            sys.exit(1)
        update_config(sys.argv[2])
    elif command == "start":
        start()
    elif command == "stop":
        stop()
    elif command == "restart":
        restart()
    elif command == "status":
        status()
    elif command == "logs":
        logs()
    elif command == "update-to-version":
        update_to_version()
    elif command == "info":
        info()
    elif command == "diagnose":
        diagnose()
    elif command == "fetch-client":
        if len(sys.argv) > 2:
            fetch_client(sys.argv[2])
        fetch_client()
    else:
        slow_type(f"Unknown command: {command}")
