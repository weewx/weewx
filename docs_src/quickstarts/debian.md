# Installation on Debian-based systems 

This is a guide to installing WeeWX from a DEB package on Debian-based systems, including Ubuntu, Mint, and Raspberry Pi OS.

## Compatible operating system versions

WeeWX V5.x requires *Python v3.7 or greater*, which is only available on *Debian 10 or later*. A package installer for Python 2 is not available.

It is recommended that users of older operating systems either use WeeWX V4.x (unsupported), or install Python 3.7 or greater on their system.

## Configure `apt`

The first time you install WeeWX, you must configure `apt` so that it knows to trust weewx.com, and knows where to find the WeeWX releases.

1. Tell your system to trust weewx.com. If you see any errors, please consult the [FAQ](https://github.com/weewx/weewx/wiki/faq-apt-key-problems).

    ```shell
    wget -qO - https://weewx.com/keys.html | sudo gpg --dearmor --output /etc/apt/trusted.gpg.d/weewx.gpg
    ```

2. Run the following command to tell `apt` where to find the WeeWX Python 3 repository.

    ```shell
    echo "deb [arch=all] https://weewx.com/apt/python3 buster main" | sudo tee /etc/apt/sources.list.d/weewx.list
    ```


## Install

Having configured `apt`, you can now use it to install WeeWX. The installer will prompt for a location, latitude/longitude, altitude, station type, and parameters specific to your station hardware.

```shell
sudo apt update
sudo apt install weewx
```

When you are done, WeeWX will be running in the background as a daemon.

### Verify

After about 5 minutes (the exact length of time depends on your archive interval), cut and
paste the following into your web browser:

    /var/www/html/index.html

You should see your station information and data.

You may also want to check your system log for any problems.

## Configure

If you chose the simulator as your station type, then at some point you will
probably want to switch to using real hardware. Here's how to reconfigure.

```shell
# Stop the daemon:
sudo systemctl stop weewx
# Reconfigure to use your hardware:
sudo weectl station reconfigure
# Remove the old database:
sudo rm /var/lib/weewx/weewx.sdb
# Restart the daemon:
sudo systemctl start weewx
```

## Customize

To enable uploads, such as Weather Underground, or to customize reports, modify
the configuration file `/etc/weewx/weewx.conf`. See the [*User
Guide*](../../usersguide) and [*Customization Guide*](../../custom) for details.

WeeWX must be restarted for configuration file changes to take effect.

``` shell
sudo systemctl restart weewx
```

## Uninstall

To uninstall WeeWX, but retain configuration files and data:

```shell
sudo apt remove weewx
```

To uninstall WeeWX, removing configuration files but retaining data:

```shell
sudo apt purge weewx
```

To remove data:

```shell
sudo rm -r /var/lib/weewx
sudo rm -r /var/www/html/weewx
```
