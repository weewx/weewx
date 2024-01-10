# Running WeeWX from a git repository

Because WeeWX is pure-Python and does not need to be compiled, it can be run
directly from a git repository without "installing" it first. This approach is
perhaps most appropriate for developers, but it is also useful on older
operating systems or on platforms with tight memory and/or storage constraints.

This technique can also be used to run from a source directory expanded from a
zip/tar file.

Although you do not need root privileges to run WeeWX this way, you will need
them to set up a daemon and, perhaps, to change device permissions.

## Install pre-requisites

Before starting, you must install the pre-requisite Python and Python modules.

1. Ensure that Python 3.6 or later is installed.

2. Ensure that `pip` and `venv` are installed.

3. Create and activate a virtual environment in your home directory:

    ``` {.shell .copy}
    python3 -m venv ~/weewx-venv
    source ~/weewx-venv/bin/activate
    ```

4. Install the minimum WeeWX dependencies:

    ``` {.shell .copy}
    python3 -m pip install CT3
    python3 -m pip install configobj
    python3 -m pip install Pillow
    ```

5. If you are running Python 3.6, you must install a backport to allow 
importation of package resources:

    ``` {.shell .copy}
    # for Python 3.6 only:
    python3 -m pip install importlib-resources
    ```

6. Depending on your situation, you may want to install these additional
dependencies:

    ``` {.shell .copy}
    # If your hardware uses a serial port
    python3 -m pip install pyserial
    # If your hardware uses a USB port
    python3 -m pip install pyusb
    # If you want extended celestial information:
    python3 -m pip install ephem
    # If you use MySQL or Maria
    python3 -m pip install "PyMySQL[rsa]"
    ```

## Get the code

Use `git` to clone the WeeWX repository into a directory called `weewx` in
your home directory:

```{.shell .copy}
git clone https://github.com/weewx/weewx ~/weewx
```

!!! Note
    For systems with very little space, you may want to create a *shallow*
    clone:
    ``` {.shell .copy}
    git clone --depth 1 https://github.com/weewx/weewx ~/weewx
    ```

!!! Note
    Of course, the directory you clone into does not have to be `~/weewx`.
    It can be any directory. Just be sure to replace `~/weewx` with your
    directory's path in the rest of the instructions.


## Provision a new station

Now that you have the prerequisites and the WeeWX code, you can provision a
new station:

```{.shell .copy}
# If necessary, activate the WeeWX virtual environment
source ~/weewx-venv/bin/activate
# Provision a new station
python3 ~/weewx/src/weectl.py station create
```

The tool `weectl` will ask you a series of questions, then create a directory
`weewx-data` in your home directory with a new configuration file. It will also
install skins, utilitiy files, and examples in the same directory. The database
and reports will also go into that directory, but only after you run `weewxd`,
as shown in the following step.


## Run `weewxd`

The program `weewxd` does the data collection, archiving, uploading, and report
generation.  You can run it directly, or as a daemon.

When you run `weewxd` directly, it will print data to the screen. It will
stop when you log out, or when you terminate it with `control-c`.

```{.shell .copy}
# If necessary, activate the WeeWX virtual environment
source ~/weewx-venv/bin/activate
# Run weewxd
python3 ~/weewx/src/weewxd.py
```

To run `weewxd` as a daemon, install an init configuration that is appropriate
to your operating system, e.g., systemd service unit, SysV init script, or
launchd control file. Be sure to use the full path to the Python interpreter
and `weewxd.py` - the paths in the virtual environment. Examples are included
in the directory `~/weewx-data/util`.


## Verify

After about 5 minutes (the exact length of time depends on your archive
interval), copy the following and paste into a web browser. You should see
your station information and data.

    ~/weewx-data/public_html/index.html

!!! Note
    Not all browsers understand the tilde ("`~`") mark. You may
    have to substitute an explicit path to your home directory,
    for example, `file:///home/jackhandy` instead of `~`.

If you have problems, check the [system
log](../usersguide/monitoring.md#log-messages). See the
[*Troubleshooting*](../usersguide/troubleshooting/what-to-do.md) section of the
[*User's guide*](../usersguide/introduction.md) for more help.


## Customize

To enable uploads, or to enable other reports, modify the configuration file
`~/weewx-data/weewx.conf` using any text editor such as `nano`:

```{.shell .copy}
nano ~/weewx-data/weewx.conf
```

The reference
[*Application options*](../reference/weewx-options/introduction.md)
contains an extensive list of the configuration options, with explanations for
what they do. For more advanced customization, see the [*Customization
Guide*](../custom/introduction.md), as well as the reference [*Skin
options*](../reference/skin-options/introduction.md).
 
To install new skins, drivers, or other extensions, use the [extension
utility](../utilities/weectl-extension.md).

The executable `weewxd` must be restarted for the changes to take effect.


## Upgrade

Update the code by pulling the latest:

```{.shell .copy}
cd ~/weewx && git pull
```

Then restart `weewxd`


## Uninstall

Before you uninstall, be sure that `weewxd` is not running.

Then simply delete the git clone:

```shell
rm -rf ~/weewx
```

If desired, delete the data directory:

```shell
rm -r ~/weewx-data
```
