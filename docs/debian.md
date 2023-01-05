# WeeWX: Installation on Debian-based systems 

This is a guide to installing WeeWX from a DEB package on Debian-based systems, including Ubuntu, Mint, and Raspbian.

## Configure apt

The first time you install WeeWX, you must configure ```apt``` so that it knows to trust weewx.com, and knows where to find the WeeWX releases.

Step one: tell your system to trust weewx.com. If you see any errors, please consult the [FAQ](https://github.com/weewx/weewx/wiki/faq-apt-key-problems).

```
wget -qO - https://weewx.com/keys.html | \
  sudo gpg --dearmor --output /etc/apt/trusted.gpg.d/weewx.gpg
```

Step two: run one of the following two commands to tell `apt` where to find the appropriate WeeWX repository.

*   For Debian10 and later, use Python 3:

```
wget -qO - https://weewx.com/apt/weewx-python3.list | \
  sudo tee /etc/apt/sources.list.d/weewx.list
```

*   _or_, for Debian9 and earlier, use Python 2:

```
wget -qO - https://weewx.com/apt/weewx-python2.list | \
  sudo tee /etc/apt/sources.list.d/weewx.list
```

## Install

Having configured `apt`, you can now use `apt-get` to install WeeWX. The installer will prompt for a location, latitude/longitude, altitude, station type, and parameters specific to your station hardware.

```
sudo apt-get update
sudo apt-get install weewx
```

When you are done, WeeWX will be running in the background as a daemon.

## Status

To make sure things are running properly look in the system log for messages from WeeWX.

```
sudo tail -f /var/log/syslog
```

## Verify

After about 5 minutes, open the station web page in a web browser. You should see your station information and data. If your hardware supports hardware archiving, then how long you wait will depend on the [archive interval](usersguide.htm#archive_interval) set in your hardware.

```
[file:///var/www/html/weewx/index.html](file:///var/www/html/weewx/index.html)
```

## Customize

To enable uploads such as Weather Underground or to customize reports, modify the configuration file `/etc/weewx/weewx.conf`. See the [User Guide](usersguide.htm) and [Customization Guide](customizing.htm) for details.

WeeWX must be restarted for configuration file changes to take effect.

## Start/Stop

To start/stop WeeWX:

```
sudo /etc/init.d/weewx start
sudo /etc/init.d/weewx stop
```

## Uninstall

To uninstall WeeWX but retain configuration files and data:

```
sudo apt-get remove weewx
```

To uninstall WeeWX, removing configuration files but retaining data:

```
sudo apt-get purge weewx
```

To remove data:

```
sudo rm -r /var/lib/weewx
sudo rm -r /var/www/html/weewx
```

## Layout

The installation will result in the following layout:

  --------------------------------- --------------------------------
                        executable: /usr/bin/weewxd
                configuration file: /etc/weewx/weewx.conf
               skins and templates: /etc/weewx/skins
                  sqlite databases: /var/lib/weewx/
    generated web pages and images: /var/www/html/weewx/
                     documentation: /usr/share/doc/weewx-x.y.z/
                          examples: /usr/share/doc/weewx/examples/
                         utilities: /usr/bin/wee_*
  --------------------------------- --------------------------------

© [Copyright](copyright/) Tom Keffer

