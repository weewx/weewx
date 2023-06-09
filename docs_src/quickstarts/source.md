# Running WeeWX from source

This is a guide to running WeeWX directly from the code.  This approach is
perhaps most appropriate for developers, but it is also useful on older
operating systems or on platforms with tight memory and/or storage constraints.

Although you do not need root privileges to install and configure WeeWX, you
will need them to set up a daemon and, perhaps, to change device permissions.

## Pre-requisites

Ensure that Python 3.7 or later is installed on the system.

Ensure that the following Python modules are installed:

* ConfigObj
* Cheetah
* PIL

You may also want the following Python modules:

* serial (if your hardware uses a serial port)
* usb (if your hardware uses a USB port)
* ephem (if you want extended celestial information)


## Get the WeeWX code

To get the latest code, use `git` to clone the repository into a directory
called `weewx` in your home directory.

```shell
git clone https://github.com/weewx/weewx ~/weewx
```

For just a single WeeWX version, without the entire repository, download
then expand a release tarball:

    https://weewx.com/downloads/released_versions


## Provision a new station

Now that you have the code, create a configuration file and skins:
```shell
python3 ~/weewx/bin/weectl.py station create
```

The tool will ask you a series of questions, then create a directory
`weewx-data` in your home directory with a new configuration file. It will
also install skins, documentation, utilitiy files, and examples in the same
directory. The database and reports will also go into that directory, but
only after you run `weewxd`, as shown in the following step.


## Run `weewxd`

The program `weewxd` does the data collection, archiving, uploading, and report
generation.  You can run it directly, or as a daemon.

When you run WeeWX directly, it will print data to the screen, and WeeWX will
stop when you either control-c or log out.

```shell
python3 ~/weewx/bin/weewxd.py
```


## Verify

After about 5 minutes (the exact length of time depends on your archive
interval), copy the following and paste into a web browser. You should see
your station information and data.

    ~/weewx-data/public_html/index.html

If you have problems, check the system log for entries from `weewxd`.


## Customize

To enable uploads or to customize reports, modify the configuration file
`~/weewx-data/weewx.conf`. WeeWX must be restarted for configuration file
changes to take effect.

See the [*User Guide*](../../usersguide) and
[*Customization Guide*](../../custom) for details.


## Uninstall

Before you uninstall, be sure that `weewxd` is not running.  Then simply
delete the source tree.

```
rm -r ~/weewx
```

If desired, delete the data directory:

```shell
rm -r ~/weewx-data
```
