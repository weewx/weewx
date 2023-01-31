# Installation using pip

This is a guide to installing WeeWX using [pip](https://pip.pypa.io). It can be used to
install WeeWX on almost any operating system, including macOS.

## Requirements

- WeeWX V5.x requires Python 3.7 or greater. It cannot be run with Python 2.x.  If you are constrained by this, install WeeWX V4.10, the
  last version to support Python 2.7, Python 3.5, and Python 3.6.

- You must also have a copy of pip.

- While you will not need root privileges to install and configure WeeWX,
  you will need them to set up a daemon and, perhaps, to change device permissions.


## Preparation

If you do not already have pip on your system, you should install it first by following 
[the directions on the pip website](https://pip.pypa.io/en/stable/installation/).

For very minimal operating systems, you may have to follow these steps as well, before trying to
install WeeWX:

=== "Debian"

    ```shell
    sudo apt update && sudo apt upgrade
    sudo apt install gcc
    sudo apt install python3-dev
    # This makes the install of pyephem go more smoothly:
    python3 -m pip install wheel
    ```

=== "Redhat"
    ```shell
    sudo yum install -y gcc
    sudo yum install -y python3-devel python3-pip
    # This makes the install of pyephem go more smoothly:
    python3 -m pip install wheel
    ```


## Installation steps

Installation is a two-step process:

1. Install the software and resources using pip.
2. Create a new station configuration file `weewx.conf` using the tool `weectl`.


### Install using pip

Once the preparatory steps are out of the way, you're ready to install WeeWX using pip.

There are many ways to do this (see the wiki document [pip
install strategies](https://github.com/weewx/weewx/wiki/pip-install-strategies)
for a partial list), but the method below is one of the simplest and safest.

!!! Note
    While not strictly necessary, it's a good idea to invoke pip using `python3 -m pip`, rather 
    than simply `pip`. This way you can be sure which version of Python is being used.

```shell
python3 -m pip install weewx --user
```

When finished, the WeeWX executables will have been installed in `~/.local/bin`,
and the libraries in your Python "user" area, generally `~/.local/lib/python3.x/site-packages/`,
where `3.x` is your version of Python.

!!! Note
    You may get a warning to the effect:
          ```
          WARNING: The script wheel is installed in '/home/ubuntu/.local/bin' which is not on PATH.
          Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
          ```
    If you do, log out, then log back in.

### Create your user data

While the first step downloads everything into your local Python source tree, it
does not set up a configuration file for your station, nor does it set up the
reporting skins. That is the job of the next step, which uses the tool `weectl`. 

This step also does not require root privileges.

```shell
weectl station create
```

The tool will ask you a series of questions, then create a directory `~/weewx-data` in your home
directory with a new configuration file. It will also install skins, documentation, utilitiy files,
and examples in the same directory. After running `weewxd`, the same directory will be used to hold
the database file and any generated HTML pages. It plays a role similar to `/home/weewx` in older
versions of WeeWX but, unlike `/home/weewx`, it does not hold any code.

If you already have a `/home/weewx` and wish to reuse it, see the [Upgrading
guide](../upgrading.htm) and the [*Migrating setup.py installs to Version 5*](v5-upgrade.md).

## Running `weewxd`

### Run directly

After the last step, the main program `weewxd` can be run directly like any
other program:

```shell
weewxd
```

### Run as a daemon

If you wish to run `weewxd` as a daemon, follow the following steps, depending
on your operating system. These steps will require root privileges in order to
install the required daemon file.

=== "Debian"

    !!! Note
        The resulting daemon will be run using your username. If you prefer to use run as `root`,
        you will have to modify the file `/etc/systemd/system/weewx.service`.

    ```shell
    cd ~/weewx-data
    sudo cp util/systemd/weewx.service /etc/systemd/system
    sudo systemctl daemon-reload
    sudo systemctl enable weewx
    sudo systemctl start weewx
    ```
    
=== "Very old Debian"

    !!! Note
        The resulting daemon will be run using your username. If you prefer to use run as `root`,
        you will have to modify the file `/etc/init.d/weewx`.

    ```shell
    # Use the old init.d method if your os is ancient
    cd ~/weewx-data
    sudo cp util/init.d/weewx.debian /etc/init.d/weewx
    sudo chmod +x /etc/init.d/weewx
    sudo update-rc.d weewx defaults 98
    sudo /etc/init.d/weewx start     
    ```

=== "Redhat"

    !!! Note
        The resulting daemon will be run using your username. If you prefer to use run as `root`,
        you will have to modify the file `/etc/systemd/system/weewx.service`.

    ```shell
    # If SELinux is enabled, you will need the following command first:
    chcon -R --reference /bin/ls ~/.local/bin

    # Then proceed as normal:
    cd ~/weewx-data
    sudo cp util/systemd/weewx.service /etc/systemd/system
    sudo systemctl daemon-reload
    sudo systemctl enable weewx
    sudo systemctl start weewx
    ```

=== "SuSE"

    ```shell
    cd ~/weewx-data
    sudo cp util/init.d/weewx.suse /etc/init.d/weewx
    sudo chmod +x /etc/init.d/weewx
    sudo /usr/lib/lsb/install_initd /etc/init.d/weewx
    sudo /etc/init.d/weewx start
    ```

=== "macOS"

    ```shell
    cd ~/weewx-data
    sudo cp util/launchd/com.weewx.weewxd.plist /Library/LaunchDaemons
    sudo launchctl load /Library/LaunchDaemons/com.weewx.weewxd.plist
    ```


### Verify

After about 5 minutes (the exact length of time depends on your archive interval), open the
[station web page](file:///~/weewx-data/public_html/index.html) in a web browser. You should see
your station information and data.

!!! note 
    Clicking the link to the webpage may be blocked by your browser. If
    that's the case, cut and paste the following link into the browser:
    `~/weewx-data/public_html/index.html`

You may also want to check your system log for any problems.

## Configure

If you chose the simulator as your station type, then at some point you will
probably want to switch to using real hardware. Here's how to reconfigure.

```shell
sudo systemctl stop
# Reconfigure to use your hardware:
sudo weectl station reconfigure
# Remove the old database:
sudo rm ~/weewx-data/archive/weewx.sdb
# Restart:
sudo systemctl start
```

## Customize

To enable uploads, such as Weather Underground, or to customize reports, modify
the configuration file `~/weewx-data/weewx.conf`. See the [*User
Guide*](../usersguide) and [*Customization Guide*](../custom) for details.

WeeWX must be restarted for configuration file changes to take effect.


## Uninstall

Stop WeeWX

=== "Debian"

    ```shell
    sudo systemctl stop weewx
    sudo systemctl disable weewx
    ```

=== "Very old Debian"

    ```shell
    sudo /etc/rc.d/init.d/weewx stop
    ```

=== "Redhat"

    ```shell
    sudo systemctl stop weewx
    sudo systemctl disable weewx
    ```

=== "SuSE"

    ```shell
    sudo /etc/rc.d/init.d/weewx stop
    ```

=== "macOS"

    ```shell
    sudo launchctl unload /Library/LaunchDaemons/com.weewx.weewxd.plist
    ```

Uninstall any daemon files:

=== "Debian"

    ```shell
    sudo rm /etc/systemd/system/weewx.service
    ```

=== "Very old Debian"

    ```shell
    sudo rm /etc/init.d/weewx
    ```

=== "Redhat"

    ```shell
    sudo rm /etc/systemd/system/weewx.service
    ```

=== "SuSE"

    ```shell
    sudo rm /etc/init.d/weewx
    ```

=== "macOS"

    ```shell
    sudo rm /Library/LaunchDaemons/com.weewx.weewxd.plist
    ```

Use pip to uninstall the program.

```shell
python3 -m pip uninstall weewx -y
```

You can also use pip to uninstall the dependencies, but first check that they are
not being used by other programs!

```shell
python3 -m pip uninstall pyserial pyusb CT3 Pillow configobj PyMySQL pyephem ephem -y
```

Finally, if desired, delete the data directory:

```shell
rm -r ~/weewx-data
```
