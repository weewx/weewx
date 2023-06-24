# Installation using pip

This is a guide to installing WeeWX using [pip](https://pip.pypa.io). It can
be used to install WeeWX on almost any operating system, including macOS.

WeeWX V5 requires Python 3.7 or greater. Python 2, or earlier versions of Python 3, will not work.
If you are constrained by this, you can install WeeWX V4, which runs with Python 2.7, 3.5,
and 3.6, although it is not supported. You are best off installing Python 3.7+ on your system.

Although you do not need root privileges to install and configure WeeWX, you will need them to set
up a daemon and, perhaps, to change device permissions.

While there are many ways to install WeeWX using pip (see the wiki document [pip install
strategies](https://github.com/weewx/weewx/wiki/pip-install-strategies) for a partial list), we
recommend creating a _virtual environment_ using `venv`, because it is the least likely to disturb
the rest of your system. It's worth reading about
[`venv`](https://docs.python.org/3/library/venv.html) in the Python3 documentation.

## Install in a virtual environment

To install WeeWX in a virtual environment, follow the directions below for your system:

!!! Install

    === "Debian"
    
        _Tested with Debian 10, 12, Ubuntu 20.04, and 22.04._
    
        ```{ .shell .copy }
        sudo apt update && sudo apt upgrade
        sudo apt install python3-pip -y
        sudo apt install python3-venv -y
    
        # Create the virtual environment:
        python3 -m venv ~/weewx-venv
    
        # Activate the virtual environment:
        source ~/weewx-venv/bin/activate
    
        # Make sure pip is up to date
        python3 -m pip install pip --upgrade
    
        # Install WeeWX into the virtual environment:
        python3 -m pip install weewx
        ```
    
    === "Rocky 8"
    
        _Tested with Rocky 8.7._
        ```{ .shell .copy }
        sudo yum update
        # Check your version of Python. You must have 3.7 or later
        python3 -V
    
        # If it is less than Python 3.7, install a later version of Python.
        # For example, this would install Python 3.11.
        # Afterwards, you must remember to invoke Python using "python3.11", NOT "python3"
        sudo yum install python3.11 -y
        sudo yum install python3.11-pip -y
    
        # Create the virtual environment:
        python3.11 -m venv ~/weewx-venv
    
        # Activate the virtual environment:
        source ~/weewx-venv/bin/activate
    
        # Make sure pip is up to date
        python3.11 -m pip install pip --upgrade
    
        # Install WeeWX into the virtual environment:
        python3.11 -m pip install weewx
        ```
    
    === "Rocky 9"
    
        _Tested with Rocky 9.1 and 9.2._
        ```{ .shell .copy }
        sudo yum update
        sudo yum install python3-pip -y
    
        # Create the virtual environment:
        python3 -m venv ~/weewx-venv
    
        # Activate the virtual environment:
        source ~/weewx-venv/bin/activate
    
        # Make sure pip is up to date
        python3 -m pip install pip --upgrade
    
        # Install WeeWX into the virtual environment:
        python3 -m pip install weewx
        ```
    
    === "openSUSE"
    
        _Tested with openSUSE Leap 15.5._
        ```{ .shell .copy }
        sudo zypper refresh
        # Check your version of Python. You must have 3.7 or later
        python3 -V
    
        # If it is less than Python 3.7, install a later version of Python.
        # For example, this would install Python 3.11.
        # Afterwards, you must remember to invoke Python using "python3.11", NOT "python3"
        sudo zypper install -y python311
    
        # Create the virtual environment:
        python3.11 -m venv ~/weewx-venv
    
        # Activate the virtual environment:
        source ~/weewx-venv/bin/activate
    
        # Make sure pip is up to date
        python3.11 -m pip install pip --upgrade
    
        # Install WeeWX into the virtual environment:
        python3.11 -m pip install weewx
        ```
    
    === "macOS"
    
        _Tested on macOS 13.4 (Ventura)_
        ```{ .shell .copy }
        # Create the virtual environment:
        python3 -m venv ~/weewx-venv
    
        # Activate the virtual environment:
        source ~/weewx-venv/bin/activate
    
        # Make sure pip is up to date
        python3 -m pip install pip --upgrade
    
        # Install WeeWX into the virtual environment:
        python3 -m pip install weewx
        ```
    
    
    === "Other"
    
        Generally, WeeWX can be installed on any operating system that offers a version of
        Python 3.7 or later. 
    
        You may need to install pip. See [Installing pip with Linux Package
        Managers](https://packaging.python.org/en/latest/guides/installing-using-linux-tools/). The
        [installation directions](https://pip.pypa.io/en/stable/installation/) on the pip website 
        may also be useful.
    
        You will also need `venv`. If it is not on your system, and your Linux Package Manager does
        not offer a version, then you can substitute `virtualenv`, which can be installed using pip.


When finished, the WeeWX executables will have been installed in `~/weewx-venv/bin`, while the
WeeWX libraries and dependencies will have been installed in `~/weewx-venv/lib/python3.x/site-packages`,
where `3.x` is the version of Python you used.


## Provision a new station

While the installation instructions above download WeeWX and install it in a virtual environment,
they do not set up the configuration specific to your station, nor do they set up the reporting
skins. That is the job of the tool `weectl`. This step also does not require root privileges.

```{ .shell .copy }
# Make sure your virtual environment is still active
source ~/weewx-venv/bin/activate
# Then create the station data
weectl station create
```

The tool `weectl` will ask you a series of questions, then create a directory
`~/weewx-data` in your home directory with a new configuration file. It will
also install skins, documentation, utilitiy files, and examples in the same
directory. The database and reports will also go into that directory, but
only after you run `weewxd`, as shown in the following step.


## Run `weewxd`

The program `weewxd` does the data collection, archiving, uploading, and report
generation.  You can run it directly, or as a daemon.


### Run directly

When you run WeeWX directly, it will print data to the screen, and WeeWX will
stop when you either control-c or log out.

```{ .shell .copy }
# Make sure your virtual environment is still active
source ~/weewx-venv/bin/activate
# Then run weewxd:
weewxd
```

### Run as a daemon

To make WeeWX start when the system is booted, run `weewxd` as a daemon.
The steps to configure `weewxd` to run as a daemon depend on your operating
system, and require root privileges.

=== "systemd"

    ```{ .shell .copy }
    # Systems that use systemd, e.g., Debian, Redhat, SUSE
    sudo cp ~/weewx-data/util/systemd/weewx.service /etc/systemd/system
    sudo systemctl daemon-reload
    sudo systemctl enable weewx
    sudo systemctl start weewx
    ```

    !!! Note
        The resulting daemon will be run using your username. If you prefer to
        use run as `root`, you will have to modify the file
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

If there are problems, check the system log.


## Configure

If you chose the simulator as your station type, then at some point you will
probably want to switch to using real hardware. This is how to reconfigure.

=== "systemd"
 
    ```{ .shell .copy }
    # Stop the weewx daemon:
    sudo systemctl stop weewx
    # Make sure the WeeWX virtual environment is active
    source ~/weewx-venv/bin/activate
    # Reconfigure to use your hardware:
    weectl station reconfigure
    # Remove the old database:
    rm ~/weewx-data/archive/weewx.sdb
    # Start the weewx daemon:
    sudo systemctl start weewx
    ```

=== "sysV"

    ```{ .shell .copy }
    # Stop the weewx daemon:
    sudo /etc/init.d/weewx stop
    # Make sure the WeeWX virtual environment is active
    source ~/weewx-venv/bin/activate
    # Reconfigure to use your hardware:
    weectl station reconfigure
    # Remove the old database:
    rm ~/weewx-data/archive/weewx.sdb
    # Start the weewx daemon:
    sudo /etc/init.d/weewx start
    ```

=== "macOS"

    ```{ .shell .copy }
    # Stop the weewx daemon:
    sudo launchctl unload /Library/LaunchDaemons/com.weewx.weewxd.plist
    # Make sure the WeeWX virtual environment is active
    source ~/weewx-venv/bin/activate
    # Reconfigure to use your hardware:
    weectl station reconfigure
    # Remove the old database:
    rm ~/weewx-data/archive/weewx.sdb
    # Start the weewx daemon:
    sudo launchctl load /Library/LaunchDaemons/com.weewx.weewxd.plist
    ```


## Customize

To enable uploads or to customize reports, modify the configuration file.
Use any text editor, such as `nano`:
```shell
nano ~/weewx-data/weewx.conf
```

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

See the [*User Guide*](../../usersguide) and
[*Customization Guide*](../../custom) for details.


## Upgrade

Get the latest release using `pip`:

```{ .shell .copy }
# Make sure the WeeWX virtual environment is active
source ~/weewx-venv/bin/activate
# Upgrade the code base
python3 -m pip install weewx --upgrade
```

Optional: You may want to upgrade your documentation and examples.
```
weectl station upgrade --what docs examples util
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

    _Systems that use systemd, e.g., Debian, Redhat, SUSE_

    ```{ .shell .copy }
    sudo systemctl stop weewx
    sudo systemctl disable weewx
    sudo rm /etc/systemd/system/weewx.service
    ```

=== "sysV"

    _Systems that use SysV init, e.g., Slackware, Devuan, Puppy, DD-WRT_

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

To delete the applications and code, simply remove the WeeWX virtual environment:

```{ .shell .copy }
rm -r ~/weewx-venv
```

Finally, if desired, to delete the database, skins, and other utilities, remove the data directory:

```{ .shell .copy }
rm -r ~/weewx-data
```
