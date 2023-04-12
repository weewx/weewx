# Installation on Redhat-based systems 

This is a guide to installing WeeWX from an RPM package on systems such
as Redhat, CentOS or Fedora.

## Compatible operating system versions

WeeWX v5 requires *Python v3.7 or greater*, which is only available on *redhat-8 or later*. A package installer for Python 2 is not available.

It is recommended that users of older operating systems either use WeeWX V4.x (unsupported), or install Python 3.7 or greater on their system.

## Install pre-requisites

Unfortunately, not everything that WeeWX uses is included in the
standard Redhat repositories. You will need to enable
their respective EPEL ("Extra Packages for Enterprise Linux")
repositories, then install some prerequisites manually.

Add the EPEL repo and install prerequisites:

```shell
sudo yum install epel-release
sudo yum install python3-cheetah
```

## Configure yum

The first time you install WeeWX, you must configure `yum` so that it knows to trust weewx.com, and knows where to find the WeeWX releases.

1. Tell your system to trust weewx.com:

    ```shell
    sudo rpm --import https://weewx.com/keys.html
    ```

2. Enable the WeeWX repo:

    ```shell
    curl -s https://weewx.com/yum/weewx-el8.repo | sudo tee /etc/yum.repos.d/weewx.repo
    ```

## Install

Install WeeWX using `yum` or `dnf`. When you are done, WeeWX will be running in the background as a daemon.

```shell
sudo yum install weewx
```


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
sudo /etc/init.d/weewx stop
# Reconfigure to use your hardware:
sudo weectl station reconfigure
# Remove the old database:
sudo rm /var/lib/weewx/weewx.sdb
# Restart:
sudo /etc/init.d/weewx start
```


## Customize

To enable uploads such as Weather Underground or to customize reports,
modify the configuration file `/etc/weewx/weewx.conf`. See the
[User Guide](../../usersguide) and [Customization Guide](../../custom)
for details.

WeeWX must be restarted for configuration file changes to take effect.

## Uninstall

To uninstall WeeWX, removing configuration files but retaining data:

```
sudo yum remove weewx
```

To remove data:

```
sudo rm -r /var/lib/weewx
sudo rm -r /var/www/html/weewx
```
