#!/bin/bash

cb2_install_location="/home/ubuntu/projects/cb2-game-dev"

cd $cb2_install_location
source server/venv/bin/activate
cd server
python3 -m main
