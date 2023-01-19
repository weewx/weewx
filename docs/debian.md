# Installation on Debian-based systems 

This is a guide to installing WeeWX from a DEB package on Debian-based systems, including Ubuntu, Mint, and Raspbian.

## Compatible operating system versions

WeeWX V5.x requires Python v3.7 or greater, which is only available on *Debian 10 or later*. No package installer for Python 2 is available.

It is recommended that users of older operating systems either use WeeWX V4.x (unsupported), or install Python 3.7 or greater on their system.

## Configure `apt`

The first time you install WeeWX, you must configure `apt` so that it knows to trust weewx.com, and knows where to find the WeeWX releases.

1. Tell your system to trust weewx.com. If you see any errors, please consult the [FAQ](https://github.com/weewx/weewx/wiki/faq-apt-key-problems).

    ```shell
    wget -qO - https://weewx.com/keys.html | \
      sudo gpg --dearmor --output /etc/apt/trusted.gpg.d/weewx.gpg
    ```

2. Run the following command to tell `apt` where to find the appropriate WeeWX repository.

    ```shell
    wget -qO - https://weewx.com/apt/weewx-python3.list | \
      sudo tee /etc/apt/sources.list.d/weewx.list
    ```


## Install

Having configured `apt`, you can now use `apt-get` to install WeeWX. The installer will prompt for a location, latitude/longitude, altitude, station type, and parameters specific to your station hardware.

```shell
sudo apt-get update
sudo apt-get install weewx
```

When you are done, WeeWX will be running in the background as a daemon.

## Status

To make sure things are running properly look in the system log for messages from WeeWX.

```shell
sudo tail -f /var/log/syslog
```

## Verify

After about 5 minutes, open the station web page in a web browser. You should see your station
information and data. If your hardware supports hardware archiving, then how long you wait will
depend on option [`archive_interval`](../usersguide/weewx-config-file/stdarchive/#archive_interval)
set in your hardware.

[file:///var/www/html/weewx/index.html](file:///var/www/html/weewx/index.html)

## Configure

The default installation uses a Simulator as the `station_type`. To
use real hardware, stop WeeWX, change to the actual station type and
station parameters, delete the simulation data, then restart WeeWX:

```shell
sudo systemctl stop
sudo weectl station reconfigure
sudo rm /var/lib/weewx/weewx.sdb
sudo systemctl start
```

## Customize

To enable uploads such as Weather Underground or to customize reports, modify the configuration file `/etc/weewx/weewx.conf`. See the [*Users Guide*](../usersguide) and [*Customization Guide*](../custom) for details.

WeeWX must be restarted for changes in the configuration file to take effect.

## Start/Stop

To start/stop WeeWX:

```shell
sudo /etc/init.d/weewx start
sudo /etc/init.d/weewx stop
```

## Uninstall

To uninstall WeeWX but retain configuration files and data:

```shell
sudo apt-get remove weewx
```

To uninstall WeeWX, removing configuration files but retaining data:

```shell
sudo apt-get purge weewx
```

To remove data:

```shell
sudo rm -r /var/lib/weewx
sudo rm -r /var/www/html/weewx
```

## Layout

The installation will result in the following layout:

| Role                    | Symbolic name     | Nominal value                   |
|-------------------------|-------------------|---------------------------------|
| WeeWX root directory    | _`$WEEWX_ROOT`_   | `/`                             |
| Executables             | _`$BIN_ROOT`_     | `/usr/share/weewx/`             |
| Configuration directory | _`$CONFIG_ROOT`_  | `/etc/weewx/`                   |
| Skins and templates     | _`$SKIN_ROOT`_    | `/etc/weewx/skins/`             |
| SQLite databases        | _`$SQLITE_ROOT`_  | `/var/lib/weewx/`               |
| Web pages and images    | _`$HTML_ROOT`_    | `/var/www/html/weewx/`          |
| Documentation           | _`$DOC_ROOT`_     | `/usr/share/doc/weewx/`         |
| Examples                | _`$EXAMPLE_ROOT`_ | `/usr/share/doc/weewx/examples/`|
| User directory          | _`$USER_ROOT`_    | `/usr/share/weewx/user`         |
| PID file                |                   | `/var/run/weewx.pid`            |
| Log file                |                   | `/var/log/syslog`               |
