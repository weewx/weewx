# Installation on Redhat systems 

This is a guide to installing WeeWX from an RPM package on systems based on
Redhat, including Fedora, CentOS, or Rocky.

WeeWX V5 requires Python 3.7 or greater, which is only available on Redhat 8 or
later.  For older systems, either use WeeWX V4, or install Python 3.7 then
[install WeeWX V5 using pip](../pip).


## Install pre-requisites

Unfortunately, not everything that WeeWX uses is included in the standard
Redhat repositories. You will need to enable the EPEL repositories
("Extra Packages for Enterprise Linux") then install the WeeWX prerequisites.

Add the EPEL repository and install prerequisites:

```shell
sudo yum install epel-release
sudo yum install python3-cheetah
```


## Configure yum

The first time you install WeeWX, you must configure `yum` so that it will
trust weewx.com, and know where to find the WeeWX releases.

1. Tell your system to trust weewx.com:

    ```shell
    sudo rpm --import https://weewx.com/keys.html
    ```

2. Tell `yum` where to find the WeeWX repository.

    ```shell
    curl -s https://weewx.com/yum/weewx-el8.repo | \
        sudo tee /etc/yum.repos.d/weewx.repo
    ```


## Install

Install WeeWX using `yum` or `dnf`. When you are done, WeeWX will be running
the `Simulator` in the background as a daemon.

```shell
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

To enable uploads or to customize reports, modify the configuration file.
Use any text editor, such as `nano`:
```shell
sudo nano /etc/weewx/weewx.conf
```

WeeWX must be restarted for the changes to take effect.
```shell
sudo systemctl restart weewx
```

See the [*User Guide*](../../usersguide) and
[*Customization Guide*](../../custom) for details.


## Upgrade

Upgrade to the latest version like this:
```shell
sudo yum update weewx
```

The upgrade process will not modify the WeeWX databases.

Unmodified files will be upgraded. If modifications have been made to the
configuration, `rpm` will display a message about any differences between the
changes and the new configuration. Any new changes from the upgrade will be
noted as files with a `.rpmnew` extension and the modified files will be left
untouched.

For example, if `/etc/weewx/weewx.conf` was modified, `rpm` will present a
message something like this:

```
warning: /etc/weewx/weewx.conf created as /etc/weewx/weewx.conf.rpmnew
```


## Uninstall

To uninstall WeeWX, removing configuration files but retaining data:

```shell
sudo yum remove weewx
```

To remove data:

```shell
sudo rm -r /var/lib/weewx
sudo rm -r /var/www/html/weewx
```
