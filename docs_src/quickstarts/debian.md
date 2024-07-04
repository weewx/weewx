# Installation on Debian systems 

This is a guide to installing WeeWX from a DEB package on systems based on
Debian, including Ubuntu, Mint, and Raspberry Pi OS.

WeeWX V5 requires Python 3.6 or greater, which is only available as a Debian
package, with required modules, on Debian 10 or later.  For older systems,
install Python 3 then [install WeeWX using pip](pip.md).


## Configure `apt`

The first time you install WeeWX, you must configure `apt` so that it will
trust weewx.com, and know where to find the WeeWX releases.

1. Tell your system to trust weewx.com.

    ```{.shell .copy}
    sudo apt install -y wget gnupg
    wget -qO - https://weewx.com/keys.html | \
        sudo gpg --dearmor --output /etc/apt/trusted.gpg.d/weewx.gpg
    ```

2. Tell `apt` where to find the WeeWX repository.

    ```{.shell .copy}
    echo "deb [arch=all] https://weewx.com/apt/python3 buster main" | \
        sudo tee /etc/apt/sources.list.d/weewx.list
    ```


## Install

Use `apt` to install WeeWX. The installer will prompt for a location,
latitude/longitude, altitude, station type, and parameters specific to your
station hardware.  When you are done, WeeWX will be running in the background.

```{.shell .copy}
sudo apt update
sudo apt install weewx
```


## Verify

After about 5 minutes (the exact length of time depends on your archive
interval), copy the following and paste into a web browser.  You should see
your station information and data.

```{.copy}
/var/www/html/weewx/index.html
```

If things are not working as you think they should, check the status:
```{.shell .copy}
sudo systemctl status weewx
```
and check the [system log](../usersguide/monitoring.md#log-messages):
```{.shell .copy}
sudo journalctl -u weewx
```
See the [*Troubleshooting*](../usersguide/troubleshooting/what-to-do.md)
section of the [*User's guide*](../usersguide/introduction.md) for more help.


## Configure

If you chose the simulator as your station type, then at some point you will
probably want to switch to using real hardware. This is how to reconfigure.

```{.shell .copy}
# Stop the daemon
sudo systemctl stop weewx
# Reconfigure to use your hardware
weectl station reconfigure
# Delete the old database
rm /var/lib/weewx/weewx.sdb
# Start the daemon
sudo systemctl start weewx
```


## Customize

To enable uploads, or to enable other reports, modify the configuration file
`/etc/weewx/weewx.conf` using any text editor such as `nano`:

```{.shell .copy}
nano /etc/weewx/weewx.conf
```

The reference
[*Application options*](../reference/weewx-options/introduction.md)
contains an extensive list of the configuration options, with explanations for
what they do. For more advanced customization, see the [*Customization
Guide*](../custom/introduction.md), as well as the reference [*Skin
options*](../reference/skin-options/introduction.md).
 
To install new skins, drivers, or other extensions, use the [extension
utility](../utilities/weectl-extension.md).

WeeWX must be restarted for the changes to take effect.
```{.shell .copy}
sudo systemctl restart weewx
```


## Upgrade

Upgrade to the latest version like this:

```{.shell .copy}
sudo apt update
sudo apt install weewx
```

The upgrade process will only upgrade the WeeWX software; it does not modify
the configuration file, database, or any extensions you may have installed.

If modifications have been made to the configuration file or the skins that
come with WeeWX, you will be prompted whether you want to keep the existing,
modified files, or accept the new files. Either way, a copy of the option you
did not choose will be saved.

For example, if `/etc/weewx/weewx.conf` was modified, you will see a message
something like this:

```
Configuration file `/etc/weewx/weewx.conf'
  ==> Modified (by you or by a script) since installation.
  ==> Package distributor has shipped an updated version.
  What would you like to do about it ?  Your options are:
            Y or I  : install the package maintainer's version
            N or O  : keep your currently-installed version
              D     : show the differences between the versions
              Z     : start a shell to examine the situation
         The default action is to keep your current version.
*** weewx.conf (Y/I/N/O/D/Z) [default=N] ?
```

Choosing `Y` or `I` (install the new version) will place the old
configuration in `/etc/weewx/weewx.conf.dpkg-old`, where it can be
compared with the new version in `/etc/weewx/weewx.conf`.

Choosing `N` or `O` (keep the current version) will place the new
configuration in `/etc/weewx/weewx.conf.X.Y.Z`, where `X.Y.Z` is the
new version number. It can then be compared with your old version which
will be in `/etc/weewx/weewx.conf`.

!!! Note
    In most cases you should choose `N` (the default).  Since WeeWX releases
    are almost always backward-compatible with configuration files and skins,
    choosing to keep the currently-installed version will ensure that your
    system works as it did before the upgrade.  After the upgrade, you can
    compare the new files to your existing, operational files at your leisure.


## Uninstall

To uninstall WeeWX, but retain configuration files and data:

```{.shell .copy}
sudo apt remove weewx
```

To uninstall WeeWX, deleting configuration files but retaining data:

```{.shell .copy}
sudo apt purge weewx
```

When you use `apt` to uninstall WeeWX, it does not touch WeeWX data, logs,
or any changes you might have made to the WeeWX configuration.  It also leaves
the `weewx` user, because data and configuration files were owned by that user.
To remove every trace of WeeWX:

```{.shell .copy}
sudo apt purge weewx
sudo rm -r /var/www/html/weewx
sudo rm -r /var/lib/weewx
sudo rm -r /etc/weewx
sudo rm /etc/default/weewx
sudo gpasswd -d $USER weewx
sudo userdel weewx
sudo groupdel weewx
sudo rm /etc/apt/trusted.gpg.d/weewx.gpg
sudo rm /etc/apt/sources.list.d/weewx.list
```
