# Installation using pip

This is a guide to installing WeeWX using [pip](https://pip.pypa.io). It can be used to
install WeeWX on almost any operating system, including macOS.

## Requirements

- You must have Python 3.7 or later. WeeWX V5 cannot be installed by earlier
  versions of Python. If you are constrained by this, install WeeWX V4.9, the
  last version to support Python 2.7, Python 3.5, and Python 3.6.

- You must also have a copy of pip. Nowadays, almost all versions of Python come
  with pip, however, if yours does not, see the 
  [_pip Install guide_](https://pip.pypa.io/en/stable/installation/).

- While you will not need root privileges to install and configure WeeWX,
  you will need them to set up a daemon.


## Installation steps

Installation is a two-step process:

1. Install the software and resources using pip.
2. Create a new station configuration file `weewx.conf` using the tool `weectl`.

### Install using pip

There are many ways to install WeeWX using pip (see the wiki document [pip
install strategies](https://github.com/weewx/weewx/wiki/pip-install-strategies)
for a partial list), but the method below is one of the simplest and safest. It
uses the tool [pipx](https://pypa.github.io/pipx/) to install WeeWX in a virtual
environment under your home directory. It does not require root privileges, and
it will not touch the rest of your Python environment.

```shell
# Install the tool pipx as a 'user' app
python3 -m pip install pipx --user
# Then use it to install weewx
pipx install weewx
```

When finished, the WeeWX executables will have been installed in `~/.local/bin`,
and the libraries in a virtual environment under `~/.local/pipx/venvs/weewx`.


### Create `weewx.conf`

While the first step downloads everything into your local Python source tree, it
does not set up a configuration file for your station, nor does it set up the
reporting skins. That is the job of the next step, using the tool `weectl`. 

This step also does not require root privileges.

```shell
weectl station create
```

This will create a directory `~/weewx-data` in your home directory with a new
configuration file. It will also install skins, documentation, and examples. The
same directory will be used to hold the database file and any generated HTML
pages. It plays a role similar to `/home/weewx` in older versions of WeeWX but,
unlike `/home/weewx`, it does not hold any code.

If you already have a `/home/weewx` and wish to reuse it, see the [Upgrading
guide](upgrading.md) and the [Version 5 Migration guide](v5-upgrade.md).

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
install the required daemon file..

=== "Debian"

    ```bash
    cd ~
    sudo ./.local/bin/weectl daemon install --type=systemd
    sudo systemctl enable weewx
    sudo systemctl start weewx
    ```
    
=== "Very old Debian"
    ```bash
    # Use the old init.d method if your os is ancient
    cd ~
    sudo ./.local/bin/weectl daemon install --type=sysv
    sudo /etc/init.d/weewx start
    ```

=== "Redhat"

    ```bash
    cd ~
    sudo ./.local/bin/weectl daemon install --type=sysv
    sudo chkconfig weewx on
    sudo /etc/rc.d/init.d/weewx start
    ```

=== "SuSE"

    ```bash
    cd ~
    sudo ./.local/bin/weectl daemon install --type=sysv
    sudo /etc/init.d/weewx start
    ```

=== "macOS"

    ```bash
    cd ~
    sudo ./.local/bin/weectl daemon install --type=mac
    sudo launchctl load /Library/LaunchDaemons/com.weewx.weewxd.plist
    ```


### Verify

After about 5 minutes, open the [station web
page](file:///~/weewx-data/public_html/index.html) in a web browser. You should
see your station information and data. If your hardware supports hardware
archiving, then how long you have to wait will depend on the [archive
interval](usersguide.md#archive_interval) set in your hardware.

!!! note 
    Clicking the link to the webpage may be blocked by your browser. If
    that's the case, cut and paste the following link into the browser:
    `~/weewx-data/public_html/index.html`

## Customize

To enable uploads, such as Weather Underground, or to customize reports, modify
the configuration file `~/weewx-data/weewx.conf`. See the [User
Guide](usersguide.md) and [Customization Guide](customization.md) for details.

<p>WeeWX must be restarted for configuration file changes to take effect.
</p>


## Uninstall

Stop WeeWX

=== "Debian"

    ```bash
    sudo systemctl stop weewx
    sudo systemctl disable weewx
    ```

=== "Redhat & SuSE"

    ```bash
    sudo /etc/rc.d/init.d/weewx stop
    ```

=== "macOS"

    ```bash
    sudo launchctl unload /Library/LaunchDaemons/com.weewx.weewxd.plist
    ```

Uninstall any daemon files:

```bash
cd ~
sudo ./.local/bin/weectl daemon uninstall
```

Have pipx uninstall weewx and its virtual environment:

```bash
pipx uninstall weewx
```

Finally, if desired, delete the data directory:

```bash
rm -r ~/weewx-data
```

