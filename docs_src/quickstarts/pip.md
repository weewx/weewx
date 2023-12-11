# Installation using pip

This is a guide to installing WeeWX using [`pip`](https://pip.pypa.io). It can
be used on almost any operating system (including macOS) that offers Python
v3.7 or greater. Python 2, or earlier versions of Python 3, will not work.

Although you do not need root privileges to install and configure WeeWX using
`pip`, you will need them to set up a daemon, and you may need them to change
device permissions.

While there are many ways to install WeeWX using `pip` (see the wiki document
[_`pip` install strategies_](https://github.com/weewx/weewx/wiki/pip-install-strategies)
for a partial list), we recommend creating a _Python virtual environment_,
because it is the least likely to disturb the rest of your system. It is
worth reading about
[`venv`](https://docs.python.org/3/library/venv.html),
the module used to create a virtual environment, in the Python3 documentation.

!!! Note
    You may need to install `pip` and `venv` first. This usually involves a 
    command such as

        sudo apt install python3-pip python3-venv

    See [Installing `pip` with
    Linux Package Managers](https://packaging.python.org/en/latest/guides/installing-using-linux-tools/).


## Install in a virtual environment

To install WeeWX in a virtual environment, follow the directions below for
your system. If you plan to use MySQL or MariaDB, be sure to see the
`MySQL/MariaDB` tab as well.

When you are finished, the WeeWX executables and dependencies will have been
installed inside the virtual environment.

=== "Debian"
    
    ```{ .shell .copy }
    sudo apt update
    # If necessary, install pip and venv
    sudo apt install python3-pip -y
    sudo apt install python3-venv -y
    # Create the virtual environment
    python3 -m venv ~/weewx-venv
    # Activate the WeeWX virtual environment
    source ~/weewx-venv/bin/activate
    # Install WeeWX into the virtual environment
    python3 -m pip install weewx
    ```
    _Tested with Debian 10, 12, RPi OS 32-bit, Ubuntu 20.04, and 22.04._

=== "Redhat 8"

    ```{ .shell .copy }
    sudo yum update
    # Check your version of Python. You must have 3.7 or later
    python3 -V
    # If it is less than Python 3.7, install a later version of Python.
    # For example, this would install Python 3.11. Afterwards, you must
    # remember to invoke Python using "python3.11", NOT "python3"
    sudo yum install python3.11 -y
    sudo yum install python3.11-pip -y
    # Create the virtual environment
    python3.11 -m venv ~/weewx-venv
    # Activate the WeeWX virtual environment
    source ~/weewx-venv/bin/activate
    # Install WeeWX into the virtual environment
    python3.11 -m pip install weewx
    ```
    _Tested with Rocky 8.7._

=== "Redhat 9"

    ```{ .shell .copy }
    sudo yum update
    sudo yum install python3-pip -y
    # Create the virtual environment
    python3 -m venv ~/weewx-venv
    # Activate the WeeWX virtual environment
    source ~/weewx-venv/bin/activate
    # Install WeeWX into the virtual environment
    python3 -m pip install weewx
    ```
    _Tested with Rocky 9.1 and 9.2._

=== "openSUSE"

    ```{ .shell .copy }
    sudo zypper refresh
    # Check your version of Python. You must have 3.7 or later
    python3 -V
    # If it is less than Python 3.7, install a later version of Python.
    # For example, this would install Python 3.11. Afterwards, you must
    # remember to invoke Python using "python3.11", NOT "python3"
    sudo zypper install -y python311
    # Create the virtual environment
    python3.11 -m venv ~/weewx-venv
    # Activate the WeeWX virtual environment
    source ~/weewx-venv/bin/activate
    # Install WeeWX into the virtual environment
    python3.11 -m pip install weewx
    ```
    _Tested with openSUSE Leap 15.5._

=== "macOS"

    ```{ .shell .copy }
    # Create the virtual environment
    python3 -m venv ~/weewx-venv
    # Activate the WeeWX virtual environment
    source ~/weewx-venv/bin/activate
    # Install WeeWX into the virtual environment
    python3 -m pip install weewx
    ```
    _Tested on macOS 13.4 (Ventura)_    

=== "Other"

    ```{ .shell .copy }
    # Create the virtual environment
    python3 -m venv ~/weewx-venv
    # Activate the WeeWX virtual environment
    source ~/weewx-venv/bin/activate
    # Install WeeWX into the virtual environment
    python3 -m pip install weewx
    ```

=== "MySQL/MariaDB"

    If you plan on using MySQL or MariaDB with `sha256_password` or
    `caching_sha2_password` authentication, you will also need to install
    the module `cryptography`. On some operating systems this can be a bit
    of a struggle, but the following usually works. The key step is to update
    `pip` before trying the install.
    
    ```{.shell .copy}
    # Activate the WeeWX virtual environment
    source ~/weewx-venv/bin/activate
    # Make sure pip is up-to-date
    python3 -m pip install pip --upgrade
    # Install cryptography
    python3 -m pip install cryptography
    ```


## Provision a new station

While the instructions above install WeeWX, they do not set up the
configuration specific to your station, nor do they set up the reporting
skins. That is the job of the tool `weectl`.

```{ .shell .copy }
# Activate the WeeWX virtual environment
source ~/weewx-venv/bin/activate
# Create the station data
weectl station create
```

The tool `weectl` will ask you a series of questions, then create a directory
`weewx-data` in your home directory with a new configuration file. It will
also install skins, documentation, utility files, and examples in the same
directory. The database and reports will also go into that directory, but
only after you run `weewxd`, as shown in the following step.


## Run `weewxd`

The program `weewxd` does the data collection, archiving, uploading, and
report generation.  You can run it directly, or as a daemon.


### Run directly

When you run WeeWX directly, it will print data to the screen. WeeWX will
stop when you log out, or when you terminate it with `control-c`.

```{ .shell .copy }
# Activate the WeeWX virtual environment
source ~/weewx-venv/bin/activate
# Run weewxd
weewxd
```

### Run as a daemon

To make WeeWX start when the system is booted, you will want to run `weewxd`
as a daemon. Follow the directions below for your system. You will need root
privileges.

=== "systemd"

    ```{ .shell .copy }
    # For systems that use systemd, e.g., Debian, Redhat, SUSE, run the
    # provided script:
    sudo ~/weewx-data/scripts/setup-daemon.systemd
    # Now start the daemon:
    sudo systemctl start weewx
    ```

    !!! Note
        The resulting daemon will be run using your username. If you prefer to
        use run as `root`, you will have to modify the unit file
        `/etc/systemd/system/weewx.service`.
    
=== "sysV"

    ```{ .shell .copy }
    # Systems that use SysV init, e.g., Slackware, Devuan, Puppy, DD-WRT
    sudo cp ~/weewx-data/util/init.d/weewx.debian /etc/init.d/weewx
    sudo chmod +x /etc/init.d/weewx
    sudo update-rc.d weewx defaults 98
    sudo /etc/init.d/weewx start     
    ```

    !!! Note
        The resulting daemon will be run using your username. If you prefer to
        use run as `root`, you will have to modify the file
        `/etc/init.d/weewx`.

=== "macOS"

    ```{ .shell .copy }
    sudo cp ~/weewx-data/util/launchd/com.weewx.weewxd.plist /Library/LaunchDaemons
    sudo launchctl load /Library/LaunchDaemons/com.weewx.weewxd.plist
    ```


## Verify

After about 5 minutes (the exact length of time depends on your archive
interval), copy the following and paste into a web browser. You should
see your station information and data.

    ~/weewx-data/public_html/index.html

!!! Note
    Not all browsers understand the tilde ("`~`") mark. You may
    have to substitute an explicit path to your home directory,
    for example, `file:///home/jackhandy` instead of `~`.

If you have problems, check the system log for entries from `weewxd`.


## Configure

If you chose the simulator as your station type, then at some point you will
probably want to switch to using real hardware. This is how to reconfigure.

=== "systemd"
 
    ```{ .shell .copy }
    # Stop the weewx daemon:
    sudo systemctl stop weewx
    # Activate the WeeWX virtual environment
    source ~/weewx-venv/bin/activate
    # Reconfigure to use your hardware
    weectl station reconfigure
    # Remove the old database
    rm ~/weewx-data/archive/weewx.sdb
    # Start the weewx daemon
    sudo systemctl start weewx
    ```

=== "sysV"

    ```{ .shell .copy }
    # Stop the weewx daemon:
    sudo /etc/init.d/weewx stop
    # Activate the WeeWX virtual environment
    source ~/weewx-venv/bin/activate
    # Reconfigure to use your hardware
    weectl station reconfigure
    # Remove the old database
    rm ~/weewx-data/archive/weewx.sdb
    # Start the weewx daemon
    sudo /etc/init.d/weewx start
    ```

=== "macOS"

    ```{ .shell .copy }
    # Stop the weewx daemon:
    sudo launchctl unload /Library/LaunchDaemons/com.weewx.weewxd.plist
    # Activate the WeeWX virtual environment
    source ~/weewx-venv/bin/activate
    # Reconfigure to use your hardware
    weectl station reconfigure
    # Remove the old database
    rm ~/weewx-data/archive/weewx.sdb
    # Start the weewx daemon
    sudo launchctl load /Library/LaunchDaemons/com.weewx.weewxd.plist
    ```


## Customize

To enable uploads, or to enable other reports, modify the configuration file
`~/weewx-data/weewx.conf` using any text editor such as `nano`:

```{.shell .copy}
nano ~/weewx-data/weewx.conf
```

See the [*User's Guide*](../usersguide/introduction.md) and the reference
[*The configuration file
weewx.conf*](../reference/weewx-options/introduction.md) for
instructions.

For more advanced customization, see the  [*Customization
Guide*](../custom/introduction.md), as well as the [reference for skin
options](../reference/skin-options/introduction.md).
 
To install new skins, drivers, or other extensions, use the utility [`weectl
extension`](../utilities/weectl-extension.md).

WeeWX must be restarted for the changes to take effect.

=== "systemd"
 
    ```{ .shell .copy }
    sudo systemctl restart weewx
    ```

=== "sysV"

    ```{ .shell .copy }
    sudo /etc/init.d/weewx stop
    sudo /etc/init.d/weewx start
    ```

=== "macOS"

    ```{ .shell .copy }
    sudo launchctl unload /Library/LaunchDaemons/com.weewx.weewxd.plist
    sudo launchctl load /Library/LaunchDaemons/com.weewx.weewxd.plist
    ```


## Upgrade

Get the latest release using `pip`:

```{ .shell .copy }
# Activate the WeeWX virtual environment
source ~/weewx-venv/bin/activate
# Upgrade the WeeWX code
python3 -m pip install weewx --upgrade
```

Optional: You may want to upgrade examples and utility files:
```
weectl station upgrade --what examples util
```

Optional: You may want to upgrade your skins, although this may break or
remove modifications you have made to them. Your old skins will be saved
in a timestamped directory.
```
weectl station upgrade --what skins
```

Optional: You may want to upgrade your configuration file.  This is only
necessary in the rare case that a new WeeWX release is not backward
compatible with older configuration files.
```
weectl station upgrade --what config
```


## Uninstall

Before you uninstall, be sure that `weewxd` is not running.

If you installed a daemon configuration, remove it.

=== "systemd"

    ```{ .shell .copy }
    sudo systemctl stop weewx
    sudo systemctl disable weewx
    sudo rm /etc/systemd/system/weewx.service
    ```

=== "sysV"

    ```{ .shell .copy }
    sudo /etc/rc.d/init.d/weewx stop
    sudo update-rc.d weewx remove
    sudo rm /etc/init.d/weewx
    ```

=== "macOS"

    ```{ .shell .copy }
    sudo launchctl unload /Library/LaunchDaemons/com.weewx.weewxd.plist
    sudo rm /Library/LaunchDaemons/com.weewx.weewxd.plist
    ```

To delete the applications and code, remove the WeeWX virtual environment:

```{ .shell .copy }
rm -r ~/weewx-venv
```

Finally, if desired, to delete the database, skins, and other utilities,
remove the data directory:

```{ .shell .copy }
rm -r ~/weewx-data
```
