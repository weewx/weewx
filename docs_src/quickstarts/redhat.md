# Installation on Redhat systems 

This is a guide to installing WeeWX from an RPM package on systems based on
Redhat, including Fedora, CentOS, or Rocky.

WeeWX V5 requires Python 3.7 or greater, which is only available as a Redhat
package, with required modules, on Redhat 9 or later.  For older systems,
install Python 3.7 then [install WeeWX using pip](pip.md).


## Configure yum

The first time you install WeeWX, you must configure `yum` so that it will
trust weewx.com, and know where to find the WeeWX releases.

1. Tell your system to trust weewx.com:

    ```{.shell .copy}
    sudo rpm --import https://weewx.com/keys.html
    ```

2. Tell `yum` where to find the WeeWX repository.

    ```{.shell .copy}
    curl -s https://weewx.com/yum/weewx-el9.repo | \
        sudo tee /etc/yum.repos.d/weewx.repo
    ```


## Install

Install WeeWX using `yum` or `dnf`. When you are done, WeeWX will be running
the `Simulator` in the background.

```{.shell .copy}
sudo yum install weewx
```


## Verify

After 5 minutes, copy the following and paste into a web browser:

    /var/www/html/weewx/index.html

You should see simulated data.

Check the system log `/var/log/messages` for problems.


## Configure

To switch from the `Simulator` to real hardware, reconfigure the driver.

```shell
# Stop the daemon
sudo systemctl stop weewx
# Reconfigure to use your hardware
sudo weectl station reconfigure
# Delete the old database
sudo rm /var/lib/weewx/weewx.sdb
# Start the daemon:
sudo systemctl start weewx
```


## Customize

To enable uploads or to customize reports, modify the configuration file.
See the [*Customization Guide*](../custom/introduction.md) for instructions,
and the [application](../reference/weewx-options/introduction.md) and
[skin](../reference/skin-options/introduction.md) references for all
the options. Use any text editor, such as `nano`:

```shell
sudo nano /etc/weewx/weewx.conf
```

To install new skins, drivers, or other extensions, use the `weectl` utility
and the URL to the extension.

```shell
sudo weectl extension install https://github.com/path/to/extension.zip
```

WeeWX must be restarted for the changes to take effect.
```{.shell .copy}
sudo systemctl restart weewx
```


## Upgrade

The upgrade process will only upgrade the WeeWX software; it does not modify
the database, configuration file, extensions, or skins.

Upgrade to the latest version like this:
```{.shell .copy}
sudo yum update weewx
```

Unmodified files will be upgraded. If modifications have been made to any
files, you will see a message about any differences between the modified
files and the new files. Any new changes from the upgrade will be noted as
files with a `.rpmnew` extension and the modified files will be left untouched.

For example, if `/etc/weewx/weewx.conf` was modified, `rpm` will present a
message something like this:

```
warning: /etc/weewx/weewx.conf created as /etc/weewx/weewx.conf.rpmnew
```


## Uninstall

To uninstall WeeWX, deleting configuration files but retaining data:

```{.shell .copy}
sudo yum remove weewx
```

When you use `yum` to uninstall WeeWX, it does not touch WeeWX data, logs,
or any changes you might have made to the WeeWX configuration.  It also leaves
the `weewx` user, since data and configuration files were owned by that user.
To remove the remaining WeeWX bits:

```{.shell .copy}
sudo yum remove weewx
sudo rm -r /var/www/html/weewx
sudo rm -r /var/lib/weewx
sudo rm -r /var/log/weewx
sudo rm -r /etc/weewx
sudo userdel weewx
```
