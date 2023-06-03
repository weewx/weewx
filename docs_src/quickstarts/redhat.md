# Installation on Redhat-based systems 

This is a guide to installing WeeWX from an RPM package on Redhat-based systems
including Fedora, CentOS, or Rocky.

WeeWX V5 requires Python 3.7 or greater, which is only available on Redhat 8 or
later.  For Redhat systems older than 8, either use WeeWX V4, or install Python
3.7 then install WeeWX V5 using pip.


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
    curl -s https://weewx.com/yum/weewx-el8.repo | sudo tee /etc/yum.repos.d/weewx.repo
    ```


## Install

Install WeeWX using `yum` or `dnf`. When you are done, WeeWX will be running
the `Simulator` in the background as a daemon.

```shell
sudo yum install weewx
```


### Verify

After about 5 minutes (the exact length of time depends on your archive
interval), copy the following and into a web browser:

    /var/www/html/index.html

You should see your station information and data.

Check the system log `/var/log/messages` for problems.


## Configure

At some point you will want to switch from the `Simulator` to real hardware.
This is how to reconfigure.

```shell
# Stop the daemon:
sudo systemctl stop weewx
# Reconfigure to use your hardware:
sudo weectl station reconfigure
# Remove the old database:
sudo rm /var/lib/weewx/weewx.sdb
# Restart:
sudo systemctl start weewx
```


## Customize

To enable uploads or to customize reports, modify the configuration file
`/etc/weewx/weewx.conf`. See the [User Guide](../../usersguide) and
[Customization Guide](../../custom) for details.

WeeWX must be restarted for configuration file changes to take effect.

```shell
sudo systemctl restart weewx
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
