Cerealbar SystemD Service
=========================

This folder contains a SystemD config + launch script for launching the Cerealbar service.

Install
-------

```
sudo cp cerealbar.service /etc/systemd/system
sudo systemctl start cerealbar
```

Service Management
------------------

To see service logs:

```
journalctl -u cerealbar
```

To see service status:

```
sudo systemctl status cerealbar
```

Restart service:

```
sudo systemctl restart cerealbar
```

Stop service:

```
sudo systemctl stop cerealbar
```

Start service on boot:

```
sudo systemctl enable cerealbar
```
