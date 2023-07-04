# Running WeeWX from a git repository

Because WeeWX is pure-Python and does not need to be compiled, it can be run directly from a source
repository without "installing" it first. This approach is perhaps most appropriate for developers,
but it is also useful on older operating systems or on platforms with tight memory and/or storage
constraints.

The same technique can be used to run from a source directory downloaded as a zip file from
the WeeWX GitHub repository.

Although you do not need root privileges to run WeeWX this way, you will need them to set up a
daemon and, perhaps, to change device permissions.

## Install pre-requisites

Unlike the other install methods, running WeeWX directly from a git clone will require you to
install the pre-requisites manually. Here's how.

1. Ensure that Python 3.7 or later is installed. You will also need pip and `venv`.

2. Set up and activate a virtual environment in your home directory

    ``` {.shell .copy}
    python3 -m venv ~/weewx-venv
    source ~/weewx-venv/bin/activate
    ```

3. Make sure pip is up-to-date

    ``` {.shell .copy}
    python3 -m pip install pip --upgrade
    ```
   
4. Install the minimum dependencies

    ``` {.shell .copy}
    python3 -m pip install CT3 -y
    python3 -m pip install configobj -y
    python3 -m pip install Pillow -y
    ```

5. Depending on your situation, you may want to install these additional dependencies:

    ``` {.shell .copy}
    # If your hardware uses a serial port
    python3 -m pip install pyserial -y
    # If your hardware uses a USB port
    python3 -m pip install pyusb -y
    # If you want extended celestial information:
    python3 -m pip install ephem -y
    # If you use MySQL or Maria
    python3 -m pip install PyMySQL[rsa]
    ```

## Get the code

Use `git` to clone the repository into a directory called `weewx` in your home
directory.

```shell
git clone https://github.com/weewx/weewx ~/weewx
```

!!! Note
    For systems with very little space, you may want to create a *shallow* clone:
    ``` {.shell .copy}
    git clone --depth 1 https://github.com/weewx/weewx ~/weewx
    ```


## Provision a new station

Now that you have the code, create a configuration file and skins:
```{.shell .copy}
# Make sure your virtual environment is still active:
source ~/weewx-venv/bin/activate
# Then create the station data
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

When you run `weewxd` directly, it will print data to the screen. It will stop when you either 
control-c or log out.

```{.shell .copy}
# Make sure your virtual environment is still active:
source ~/weewx-venv/bin/activate
# Run weewxd
python3 ~/weewx/bin/weewxd.py
```

To run `weewxd` as a daemon, install a systemd or init file that is appropriate for your operating
system. Be sure to use the full path in the virtual environment to the Python interpreter and
`weewx.py`. Examples are included in the `util` directory.


## Verify

After about 5 minutes (the exact length of time depends on your archive
interval), copy the following and paste into a web browser. You should see
your station information and data.

    ~/weewx-data/public_html/index.html

!!! Note
    Not all browsers understand the tilde ("`~`") mark. You may
    have to substitute an explicit path to your home directory.

If you have problems, check the system log for entries from `weewxd`.


## Customize

To enable uploads or to customize reports, modify the configuration file.
Use any text editor, such as `nano`:

    nano ~/weewx-data/weewx.conf

The executable `weewxd` must be restarted for the changes to take effect.

See the [*User Guide*](../../usersguide) and [*Customization Guide*](../../custom) for details.


## Upgrade

Update the code by pulling the latest:
```shell
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
