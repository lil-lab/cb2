sudo apt install python3.8-venv
sudo apt install gcc
sudo apt install sqlite3 libsqlite3-dev
sudo apt install python-dev cython python3-pip
sudo apt-get install python3-dev
cd ../server/
sudo -S -u ubuntu -E env PATH=$PATH python3 -m venv --system-site-packages venv
. ./venv/bin/activate
sudo -S -u ubuntu -E env PATH=$PATH python3 -m pip install wheel==0.37.1
sudo -S -u ubuntu -E env PATH=$PATH python3 -m pip install cython
sudo -S -u ubuntu -E env PATH=$PATH python3 -m pip install -r requirements.txt
cd ../../
sudo -S -u ubuntu -E env PATH=$PATH git clone https://github.com/coleifer/peewee.git
cd peewee
sudo -S -u ubuntu -E env PATH=$PATH python setup.py install
sudo -S -u ubuntu -E env PATH=$PATH python setup.py build_ext -i
cd ../cb2-game-dev
cd deploy/systemd
sudo ./deploy.sh

