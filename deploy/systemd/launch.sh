#!/bin/bash

cb2_install_location="/home/ubuntu/projects/cb2-game-dev"

cd $cb2_install_location
source venv/bin/activate
python3 -m cb2game.server.main
