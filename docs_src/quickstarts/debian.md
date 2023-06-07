# Installation on Debian systems 

This is a guide to installing WeeWX from a DEB package on systems based on
Debian, including Ubuntu, Mint, and Raspberry Pi OS.

WeeWX V5 requires Python 3.7 or greater, which is only available on Debian 10
or later.  For older Debian systems, either use WeeWX V4, or install Python 3.7
then install WeeWX V5 using pip.


## Configure `apt`

The first time you install WeeWX, you must configure `apt` so that it will
trust weewx.com, and know where to find the WeeWX releases.

1. Tell your system to trust weewx.com.

    ```shell
    wget -qO - https://weewx.com/keys.html | sudo gpg --dearmor --output /etc/apt/trusted.gpg.d/weewx.gpg
    ```

2. Tell `apt` where to find the WeeWX repository.

    ```shell
    echo "deb [arch=all] https://weewx.com/apt/python3 buster main" | sudo tee /etc/apt/sources.list.d/weewx.list
    ```

If you encounter errors, please consult the [FAQ](https://github.com/weewx/weewx/wiki/faq-apt-key-problems).


## Install

Use `apt to install WeeWX. The installer will prompt for a location,
latitude/longitude, altitude, station type, and parameters specific to your
station hardware.  When you are done, WeeWX will be running in the background
as a daemon.

```shell
sudo apt update
sudo apt install weewx
```


## Verify

After about 5 minutes (the exact length of time depends on your archive
interval), copy the following and paste into a web browser:

    /var/www/html/index.html

You should see your station information and data.

Check the system log `/var/log/syslog` for problems.


## Configure

If you chose the simulator as your station type, then at some point you will
probably want to switch to using real hardware. This is how to reconfigure.

```shell
# Stop the daemon:
sudo systemctl stop weewx
# Reconfigure to use your hardware:
sudo weectl station reconfigure
# Remove the old database:
sudo rm /var/lib/weewx/weewx.sdb
# Start the daemon:
sudo systemctl start weewx
```


## Customize

To enable uploads or to customize reports, modify the configuration file
`/etc/weewx/weewx.conf`. See the [*User Guide*](../usersguide) and
[*Customization Guide*](../custom) for details.

WeeWX must be restarted for configuration file changes to take effect.

```shell
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
