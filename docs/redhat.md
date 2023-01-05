# WeeWX: Installation on Redhat-based systems 

This is a guide to installing WeeWX from an RPM package on systems such
as Redhat, CentOS or Fedora.

This requires a version of the operating system based on Redhat 8 or newer.

## Compatible Operating System Versions
WeeWX v5 requires python v3.7, which is only available on operating systems based on redhat-8 or later. No packages for python2-only operating systems will be provided.

It is recommended that users of older operating systems continue to use WeeWX v4 until you can update your operating system to a more current version supporting python v3.7 at a minimum.


## Install pre-requisites

Unfortunately, not everything that WeeWX uses is included in the
standard Redhat repositories. You will need to enable
their respective EPEL ("Extra Packages for Enterprise Linux")
repositories, then install some prerequisites manually.

Add the EPEL repo and install prerequisites:

```
sudo yum install epel-release
sudo yum install python3-cheetah
```

## Configure yum

Tell `yum` or `dnf` where to find the WeeWX releases.

This only has to be done once - the first time you install WeeWX.

Tell your system to trust weewx.com:

```
sudo rpm --import https://weewx.com/keys.html
```

Enable the WeeWX repo:

```
curl -s https://weewx.com/yum/weewx-el8.repo | sudo tee /etc/yum.repos.d/weewx.repo
```

## Install WeeWX

Install WeeWX using `yum` or `dnf`. When you are done,
WeeWX will be running the Simulator in the background as a daemon.

```
sudo yum install weewx
```

## Status

Look in the system log for messages from WeeWX.

```
sudo tail -f /var/log/messages
```

## Verify

After 5 minutes, open the station web page in a web browser. You should
see generic station information and data. If your hardware supports
hardware archiving, then how long you wait will depend on the [archive
interval](usersguide.md#archive_interval) set in your hardware.

``` tty
file:///var/www/html/weewx/index.html
```

## Configure

The default installation uses Simulator as the `station_type`. To
use real hardware, stop WeeWX, change to the actual station type and
station parameters, delete the simulation data, then restart WeeWX:

```
sudo /etc/init.d/weewx stop
sudo wee_config --reconfigure
sudo rm /var/lib/weewx/weewx.sdb
sudo /etc/init.d/weewx start
```

## Start/Stop

To start/stop WeeWX:

```
sudo /etc/init.d/weewx start
sudo /etc/init.d/weewx stop
```

## Customize

To enable uploads such as Weather Underground or to customize reports,
modify the configuration file `/etc/weewx/weewx.conf`. See the
[User Guide](../usersguide) and [Customization Guide](../customizing)
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

