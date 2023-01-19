# Installation on SuSE-based systems 

This is a guide to installing WeeWX from an RPM package on systems such as SuSE or OpenSUSE.

## Compatible operating system versions

WeeWX V5.x requires python v3.7 or greater, which is only available on operating systems based on *SUSE-15 or later*. No package installer for Python 2 is available.

It is recommended that users of older operating systems either use WeeWX V4.x (unsupported), or install Python 3.7 or greater on their system.

## Configure zypper

Tell zypper where to find the WeeWX releases. This only has to be done once: the first time you install WeeWX.

Tell your system to trust weewx.com:

```
sudo rpm --import https://weewx.com/keys.html
```

Define the repo:

```
curl -s https://weewx.com/suse/weewx-suse15.repo | \
    sudo tee /etc/zypp/repos.d/weewx.repo
```

## Install WeeWX

Install WeeWX using zypper. When you are done, WeeWX will be running in the background as a daemon.

```
sudo zypper install weewx
```

## Status

Look in the system log for messages from WeeWX.

```
sudo tail -f /var/log/messages
```

## Verify

After 5 minutes, open the station web page in a web browser. You should see generic station information and data. If your hardware supports hardware archiving, then how long you wait will depend on the   [archive
interval](usersguide#archive_interval) set in your hardware.

[file:///var/www/html/weewx/index.html](file:///var/www/html/weewx/index.html)

## Configure

The default installation uses Simulator as the station type. To use real hardware, stop WeeWX, change to the actual station type and station parameters, delete the database, then restart WeeWX:

```shell
sudo systemctl stop weewx
sudo weectl station reconfigure
sudo rm /var/lib/weewx/weewx.sdb
sudo systemctl start weewx
```

## Start/Stop

To start/stop WeeWX:

```shell
sudo systemctl start weewx
sudo systemctl stop weewx
```

## Customize

To enable uploads such as Weather Underground or to customize reports, modify the configuration file `/etc/weewx/weewx.conf`. See the [*Users Guide*](../usersguide) and [*Customization Guide*](../custom) for details.

WeeWX must be restarted for configuration file changes to take effect.

## Uninstall

To uninstall WeeWX, removing configuration files but retaining data:

```shell
sudo zypper remove weewx
```
To remove data:

```shell
sudo rm -r /var/lib/weewx
sudo rm -r /var/www/html/weewx
```

## Layout

The installation will result in the following layout:

| Role                    | Symbolic name     | Nominal value                          |
|-------------------------|-------------------|----------------------------------------|
| WeeWX root directory    | _`$WEEWX_ROOT`_   | `/`                                    |
| Executables             | _`$BIN_ROOT`_     | `/usr/share/weewx/`                    |
| Configuration directory | _`$CONFIG_ROOT`_  | `/etc/weewx/`                          |
| Skins and templates     | _`$SKIN_ROOT`_    | `/etc/weewx/skins/`                    |
| SQLite databases        | _`$SQLITE_ROOT`_  | `/var/lib/weewx/`                      |
| Web pages and images    | _`$HTML_ROOT`_    | `/var/www/html/weewx/`                 |
| Documentation           | _`$DOC_ROOT`_     | `/usr/share/doc/weewx-x.y.z/`          |
| Examples                | _`$EXAMPLE_ROOT`_ | `/usr/share/doc/weewx-x.y.z/examples/` |
| User directory          | _`$USER_ROOT`_    | `/usr/share/weewx/user`                |
| PID file                |                   | `/var/run/weewx.pid`                   |
| Log file                |                   | `/var/log/syslog`                      |
