
WeeWX: Installation on SuSE-based systems 
=================================================================================================

This is a guide to installing WeeWX from an RPM package on systems such as SuSE or OpenSUSE.

Configure zypper
----------------

Tell zypper where to find the WeeWX releases. This only has to be done once - the first time you install WeeWX.

Tell your system to trust weewx.com:

```
sudo rpm --import https://weewx.com/keys.html
```

For SUSE 15 use python3:

```
curl -s https://weewx.com/suse/weewx-suse15.repo | \
    sudo tee /etc/zypp/repos.d/weewx.repo
```

For SUSE 12 use python2:

```
curl -s https://weewx.com/suse/weewx-suse12.repo | \
    sudo tee /etc/zypp/repos.d/weewx.repo
```

Install WeeWX
-------------

Install WeeWX using zypper. When you are done, WeeWX will be running the Simulator in the background as a daemon.

```
sudo zypper install weewx
```

Status
------

Look in the system log for messages from WeeWX.

```
sudo tail -f /var/log/messages
```

Verify
------

After 5 minutes, open the station web page in a web browser. You should see generic station information and data. If your hardware supports hardware archiving, then how long you wait will depend on the [archive interval](usersguide.htm#archive_interval) set in your hardware.

[file:///var/www/html/weewx/index.html](file:///var/www/html/weewx/index.html)

Configure
---------

The default installation uses Simulator as the station\_type. To use real hardware, stop WeeWX, change to the actual station type and station parameters, delete the simulation data, then restart WeeWX:

```
sudo systemctl stop weewx
sudo wee_config --reconfigure
sudo rm /var/lib/weewx/weewx.sdb
sudo systemctl start weewx
```

Start/Stop
----------

To start/stop WeeWX:

sudo systemctl start weewx
sudo systemctl stop weewx

Customize
---------

To enable uploads such as Weather Underground or to customize reports, modify the configuration file /etc/weewx/weewx.conf. See the [User Guide](usersguide.htm) and [Customization Guide](customizing.htm) for details.

WeeWX must be restarted for configuration file changes to take effect.

Uninstall
---------

To uninstall WeeWX, removing configuration files but retaining data:

```
sudo zypper remove weewx

```
To remove data:


```
sudo rm -r /var/lib/weewx
sudo rm -r /var/www/html/weewx
```

Layout
------

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

