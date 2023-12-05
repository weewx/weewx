# Where to find things

## Location of WeeWX components

Here is a summary of the layout for the different install methods, along with
the symbolic names used for each component. These names are used throughout the
documentation.

=== "Debian"

    | Component               | Symbolic name    | Nominal value                   |
    |-------------------------|------------------|---------------------------------|
    | WeeWX root directory    | _`WEEWX_ROOT`_   | `/etc/weewx`                    |
    | Skins and templates     | _`SKIN_ROOT`_    | `/etc/weewx/skins/`             |
    | User directory          | _`USER_ROOT`_    | `/etc/weewx/bin/user/`          |
    | Examples                | _`EXAMPLE_ROOT`_ | `/etc/weewx/examples/`          |
    | Executables             | _`BIN_ROOT`_     | `/usr/share/weewx/`             |
    | SQLite databases        | _`SQLITE_ROOT`_  | `/var/lib/weewx/`               |
    | Web pages and images    | _`HTML_ROOT`_    | `/var/www/html/weewx/`          |
    | Documentation           | _`DOC_ROOT`_     | `/usr/share/doc/weewx/`         |

=== "RedHat"

    | Component               | Symbolic name    | Nominal value                   |
    |-------------------------|------------------|---------------------------------|
    | WeeWX root directory    | _`WEEWX_ROOT`_   | `/etc/weewx`                    |
    | Skins and templates     | _`SKIN_ROOT`_    | `/etc/weewx/skins/`             |
    | User directory          | _`USER_ROOT`_    | `/etc/weewx/bin/user/`          |
    | Examples                | _`EXAMPLE_ROOT`_ | `/etc/weewx/examples/`          |
    | Executables             | _`BIN_ROOT`_     | `/usr/share/weewx/`             |
    | SQLite databases        | _`SQLITE_ROOT`_  | `/var/lib/weewx/`               |
    | Web pages and images    | _`HTML_ROOT`_    | `/var/www/html/weewx/`          |
    | Documentation           |                  |  https://weewx.com/docs/5.0     |

=== "openSUSE"

    | Component               | Symbolic name    | Nominal value               |
    |-------------------------|------------------|-----------------------------|
    | WeeWX root directory    | _`WEEWX_ROOT`_   | `/etc/weewx`                |
    | Skins and templates     | _`SKIN_ROOT`_    | `/etc/weewx/skins/`         |
    | User directory          | _`USER_ROOT`_    | `/etc/weewx/bin/user/`      |
    | Examples                | _`EXAMPLE_ROOT`_ | `/etc/weewx/examples/`      |
    | Executables             | _`BIN_ROOT`_     | `/usr/share/weewx/`         |
    | SQLite databases        | _`SQLITE_ROOT`_  | `/var/lib/weewx/`           |
    | Web pages and images    | _`HTML_ROOT`_    | `/var/www/html/weewx/`      |
    | Documentation           |                  |  https://weewx.com/docs/5.0 |

=== "pip"

    | Component               | Symbolic name    | Nominal value               |
    |-------------------------|------------------|-----------------------------|
    | WeeWX root directory    | _`WEEWX_ROOT`_   | `~/weewx-data`              |
    | Skins and templates     | _`SKIN_ROOT`_    | `skins/`                    |
    | User directory          | _`USER_ROOT`_    | `bin/user/`                 |
    | Examples                | _`EXAMPLE_ROOT`_ | `examples/`                 |
    | Executables             | _`BIN_ROOT`_     | varies                      |
    | SQLite databases        | _`SQLITE_ROOT`_  | `archive/`                  |
    | Web pages and images    | _`HTML_ROOT`_    | `public_html/`              |
    | Documentation           |                  |  https://weewx.com/docs/5.0 |

!!! Note
    In the locations above, relative paths are *relative to _`WEEWX_ROOT`_*.
    Absolute paths begin with a forward slash (`/`).  The tilde character
    `~` represents the `HOME` directory of the user.


## Log files

In the default configuration, WeeWX logs to the system logger `syslog`. On most
systems, this puts the WeeWX messages into a file, along with other messages
from the system.

If WeeWX was installed from DEB or RPM package, then the WeeWX log messages
still use the `syslog`, but they are saved to files separate from the system's
log messages.

See the wiki article [WeeWX logging](https://github.com/weewx/weewx/wiki/WeeWX-v4-and-logging)
for more information on how to control logging in WeeWX.

This is where to find the system log.

=== "Debian"

    `/var/log/syslog`

    !!! Note
        You need root permission to view the log.

=== "RedHat"

    `/var/log/messages`

    !!! Note
        You need root permission to view the log.

=== "openSUSE"

    `/var/log/messages`

    !!! Note
        You need root permission to view the log.

=== "macOS"

    `/var/log/syslog`

    !!! note
        On macOS, the log file is likely to contain only severe log messages.


## Location of executables in a pip install

This is something you are not likely to need, but can occasionally be useful.
It's included here for completeness. If you use a pip install, the location of
the executables will depend on how the installation was done.

| Install method                                      | Commands                                                                     | Location of executables |
|-----------------------------------------------------|------------------------------------------------------------------------------|-------------------------|
| Virtual environment<br/>(recommended)               | `python3 -m venv ~/ve`<br/>`source ~/ve/bin/activate`<br/>`pip3 install weewx` | `~/ve/bin/`             |
| pip, no sudo, with `--user`                         | `pip3 install weewx --user`                                                  | `~/.local/bin/`         |
| pip, no sudo, no `--user`                           | `pip3 install weewx`                                                         | `~/.local/bin/`         |
| pip with sudo<br/>(not recommended)                 | `sudo pip3 install weewx`                                                    | `/usr/local/bin/` (1)   |
| Virtual environment with `--user`<br/>(not allowed) | `python3 -m venv ~/ve`<br/>`source ~/ve/bin/activate`<br/>`pip3 install weewx --user` | N/A                     |

(1) Checked on Ubuntu 22.02 and Rocky v9.1
