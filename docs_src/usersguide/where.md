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
    | Log                     |                  | See below                       |
    | Documentation           |                  |  https://weewx.com/docs/5.0     |

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
    | Log                     |                  | See below                       |
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
    | Log                     |                  | See below                   |
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
    | Log                     |                  | `log/weewx.log`             |
    | Documentation           |                  |  https://weewx.com/docs/5.0 |

!!! Note
    In the locations above, relative paths are *relative to _`WEEWX_ROOT`_*.
    Absolute paths begin with a forward slash (`/`).  The tilde character
    `~` represents the `HOME` directory of the user.


## Log files

Logging is configured by the `[Logging]` section in the configuration file,
`weewx.conf`. The section that comes with WeeWX Version 5 looks like this:

``` ini linenums="1" hl_lines="12 14 16"
[Logging]
    [[root]]
      handlers = timed_rotate,

    [[handlers]]
        # Log to a set of rotating files
        [[[timed_rotate]]]
            level = DEBUG
            formatter = verbose
            class = logging.handlers.TimedRotatingFileHandler
            # File to log to, relative to WEEWX_ROOT
            filename = log/weewx.log
            # When to rotate:
            when = midnight
            # How many log files to save
            backupCount = 7
```

This says to use a timed file rotation to log file `log/weewx.log` (line 12).
Note that this is _relative to `WEEWX_ROOT`_, so the actual file is likely to be
`~/weewx-data/log/weewx.log`. The file should be rotated at midnight (line 14).
A week's worth of backups should be saved (line 16).

If you don't have such a section, then the system log will
be used. This is where to find the system log for each platform.

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


See the wiki article [WeeWX V4 and logging](https://github.com/weewx/weewx/wiki/WeeWX-v4-and-logging)
for more information on controlling logging in WeeWX.


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


