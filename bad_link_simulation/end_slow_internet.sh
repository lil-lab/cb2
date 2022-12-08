echo "Warning, if you setup custom PFCTL rules, you'll need to reload them. This script just returns PFCTL to /etc/pf.conf"

pfctl -f /etc/pf.conf
