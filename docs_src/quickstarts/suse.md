# Installation on SUSE systems 

This is a guide to installing WeeWX from an RPM package systems based on SUSE,
such as openSUSE Leap.

WeeWX V5 requires Python 3.6 or greater, which is only available on SUSE-15 or
later.  For older systems, install Python 3 then
[install WeeWX using pip](pip.md).


## Configure `zypper`

The first time you install WeeWX, you must configure `zypper` so that it will
trust weewx.com, and know where to find the WeeWX releases.

1. Tell your system to trust weewx.com:

    ```{.shell .copy}
    sudo rpm --import https://weewx.com/keys.html
    ```

2. Tell `zypper` where to find the WeeWX repository.

    ```{.shell .copy}
    curl -s https://weewx.com/suse/weewx.repo | \
        sudo tee /etc/zypp/repos.d/weewx.repo
    ```


## Install

Install WeeWX using `zypper`. When you are done, WeeWX will be running the
`Simulator` in the background.

```{.shell .copy}
sudo zypper install weewx
```


## Verify

After 5 minutes, copy the following and paste into a web browser. You should
see simulated data.

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

To switch from the `Simulator` to real hardware, reconfigure the driver.

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
sudo zypper update weewx
```

The upgrade process will only upgrade the WeeWX software; it does not modify
the configuration file, database, or any extensions you may have installed.

If modifications have been made to the configuration file or the skins that
come with WeeWX, you will see a message about any differences between the
modified files and the new files. Any new changes from the upgrade will be
noted as files with a `.rpmnew` extension, and the modified files will be left
untouched.

For example, if `/etc/weewx/weewx.conf` was modified, you will see a message
something like this:

```
warning: /etc/weewx/weewx.conf created as /etc/weewx/weewx.conf.rpmnew
```


## Uninstall

To uninstall WeeWX, deleting configuration files but retaining data:

```{.shell .copy}
sudo zypper remove weewx
```

When you use `zypper` to uninstall WeeWX, it does not touch WeeWX data, logs,
or any changes you might have made to the WeeWX configuration.  It also leaves
the `weewx` user, since data and configuration files were owned by that user.
To remove every trace of WeeWX:

```{.shell .copy}
sudo zypper remove weewx
sudo rm -r /var/www/html/weewx
sudo rm -r /var/lib/weewx
sudo rm -r /etc/weewx
sudo rm /etc/default/weewx
sudo gpasswd -d $USER weewx
sudo userdel weewx
sudo groupdel weewx
```
