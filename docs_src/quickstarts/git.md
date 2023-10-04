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

1. Ensure that Python 3.7 or later is installed.

2. Ensure that you have the utility `make`.

3. Ensure that `pip` and `venv` are installed.

4. Create and activate a virtual environment in your home directory:

    ``` {.shell .copy}
    python3 -m venv ~/weewx-venv
    source ~/weewx-venv/bin/activate
    ```

5. Install the minimum WeeWX dependencies:

    ``` {.shell .copy}
    python3 -m pip install mkdocs mkdocs-material
    python3 -m pip install CT3
    python3 -m pip install configobj
    python3 -m pip install Pillow
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
    python3 -m pip install PyMySQL[rsa]
    ```

## Get the code

Use `git` to clone the WeeWX repository into a directory called `weewx` in
your home directory[^1]:

```{.shell .copy}
git clone https://github.com/weewx/weewx ~/weewx
```

!!! Note
    For systems with very little space, you may want to create a *shallow*
    clone:
    ``` {.shell .copy}
    git clone --depth 1 https://github.com/weewx/weewx ~/weewx
    ```


## Build the resources

The repository stores markdown versions of the documentation. To convert them
to HTML, you must build them:

```{.shell .copy}
cd ~/weewx
# Make sure to include the trailing slash!
make bin/wee_resources/
```

## Provision a new station

Finally, provision the configuration file, skins, and other resources for a
new station:

```{.shell .copy}
# Activate the WeeWX virtual environment
source ~/weewx-venv/bin/activate
# Create the station data
python3 ~/weewx/bin/weectl.py station create
```

The tool `weectl` will ask you a series of questions, then create a directory
`weewx-data` in your home directory with a new configuration file. It will
also install skins, documentation, utilitiy files, and examples in the same
directory. The database and reports will also go into that directory, but
only after you run `weewxd`, as shown in the following step.


## Run `weewxd`

The program `weewxd` does the data collection, archiving, uploading, and report
generation.  You can run it directly, or as a daemon.

When you run `weewxd` directly, it will print data to the screen. It will
stop when you log out, or when you terminate it with `control-c`.

```{.shell .copy}
# Activate the WeeWX virtual environment
source ~/weewx-venv/bin/activate
# Run weewxd
python3 ~/weewx/bin/weewxd.py
```

To run `weewxd` as a daemon, install a systemd or init file that is
appropriate for your operating system. Be sure to use the full path in the
virtual environment to the Python interpreter and `weewxd.py`. Examples are
included in the `util` directory.


## Verify

After about 5 minutes (the exact length of time depends on your archive
interval), copy the following and paste into a web browser. You should see
your station information and data.

    ~/weewx-data/public_html/index.html

!!! Note
    Not all browsers understand the tilde ("`~`") mark. You may
    have to substitute an explicit path to your home directory,
    for example, `file:///home/jackhandy` instead of `~`.

If you have problems, check the system log for entries from `weewxd`.


## Customize

To enable uploads or to customize reports, modify the configuration file.
See the [*Customization Guide*](../../custom/introduction) for instructions,
and the [application](../../reference/weewx-options/introduction) and
[skin](../../reference/skin-options/introduction) references for all the 
options.

    nano ~/weewx-data/weewx.conf

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

[^1]: Of course, the directory you clone into does not have to be `~/weewx`.
It can be any directory. Just be sure to replace `~/weewx` with your directory's
path in the rest of the instructions.