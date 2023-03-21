set -ex
username=$(whoami)
echo "Installing some system packages: python3.9-venv, gcc, sqlite3, cython, cargo."
sudo apt install python3 gcc sqlite3 libsqlite3-dev cython cargo unzip
echo "Setting up python env..."
echo "Your python version is: "
python3 --version
echo "If it is not 3.9+, you may experience issues running CB2."
echo "Additionally, there may be issues running 3.11+."
python3 -m venv venv
. ./venv/bin/activate
python3 -m pip install wheel
python3 -m pip install cython
python3 -m pip install -r requirements.txt
echo "Downloading client..."
cd server/www/
wget https://github.com/lil-lab/cb2/releases/download/deployed-march-2023/WebGL.zip
echo "Decompressing client."
unzip WebGL
cd -
echo "Running local self-play as a test..."
sleep 1
python3 -m py_client.demos.local_self_play --num_games=10 --config_filepath="server/config/local-covers-config.yaml"
echo "DONE"
