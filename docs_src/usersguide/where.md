# Where to find things

## Location of WeeWX components

Here is a summary of the layout for the different install methods, along with
the symbolic names used for each component. These names are used throughout the
documentation.

!!! Note
    In the locations below, relative paths are *relative to _`WEEWX_ROOT`_*.
    Absolute paths begin with a forward slash (`/`).


=== "Debian"

    | Component               | Symbolic name    | Nominal value                   |
    |-------------------------|------------------|---------------------------------|
    | WeeWX root directory    | _`WEEWX_ROOT`_   | `/`                             |
    | Executables             | _`BIN_ROOT`_     | `/usr/share/weewx/`             |
    | Configuration directory | _`CONFIG_ROOT`_  | `/etc/weewx/`                   |
    | Skins and templates     | _`SKIN_ROOT`_    | `/etc/weewx/skins/`             |
    | SQLite databases        | _`SQLITE_ROOT`_  | `/var/lib/weewx/`               |
    | Web pages and images    | _`HTML_ROOT`_    | `/var/www/html/weewx/`          |
    | Documentation           | _`DOC_ROOT`_     | `/usr/share/doc/weewx/`         |
    | Examples                | _`EXAMPLE_ROOT`_ | `/usr/share/doc/weewx/examples/`|
    | User directory          | _`USER_ROOT`_    | `/usr/share/weewx/user`         |

=== "RedHat"

    | Component               | Symbolic name    | Nominal value                          |
    |-------------------------|------------------|----------------------------------------|
    | WeeWX root directory    | _`WEEWX_ROOT`_   | `/`                                    |
    | Executables             | _`BIN_ROOT`_     | `/usr/share/weewx/`                    |
    | Configuration directory | _`CONFIG_ROOT`_  | `/etc/weewx/`                          |
    | Skins and templates     | _`SKIN_ROOT`_    | `/etc/weewx/skins/`                    |
    | SQLite databases        | _`SQLITE_ROOT`_  | `/var/lib/weewx/`                      |
    | Web pages and images    | _`HTML_ROOT`_    | `/var/www/html/weewx/`                 |
    | Documentation           | _`DOC_ROOT`_     | `/usr/share/doc/weewx-x.y.z/`          |
    | Examples                | _`EXAMPLE_ROOT`_ | `/usr/share/doc/weewx-x.y.z/examples/` |
    | User directory          | _`USER_ROOT`_    | `/usr/share/weewx/user`                |

=== "openSUSE"

    | Component               | Symbolic name    | Nominal value                          |
    |-------------------------|------------------|----------------------------------------|
    | WeeWX root directory    | _`WEEWX_ROOT`_   | `/`                                    |
    | Executables             | _`BIN_ROOT`_     | `/usr/share/weewx/`                    |
    | Configuration directory | _`CONFIG_ROOT`_  | `/etc/weewx/`                          |
    | Skins and templates     | _`SKIN_ROOT`_    | `/etc/weewx/skins/`                    |
    | SQLite databases        | _`SQLITE_ROOT`_  | `/var/lib/weewx/`                      |
    | Web pages and images    | _`HTML_ROOT`_    | `/var/www/html/weewx/`                 |
    | Documentation           | _`DOC_ROOT`_     | `/usr/share/doc/weewx-x.y.z/`          |
    | Examples                | _`EXAMPLE_ROOT`_ | `/usr/share/doc/weewx-x.y.z/examples/` |
    | User directory          | _`USER_ROOT`_    | `/usr/share/weewx/user`                |

=== "pip"

    | Component               | Symbolic name    | Nominal value        |
    |-------------------------|------------------|----------------------|
    | WeeWX root directory    | _`WEEWX_ROOT`_   | `~/weewx-data`       |
    | Executables             | _`BIN_ROOT`_     | varies               |
    | Configuration directory | _`CONFIG_ROOT`_  | `./`                 |
    | Skins and templates     | _`SKIN_ROOT`_    | `skins/`             |
    | SQLite databases        | _`SQLITE_ROOT`_  | `archive/`           |
    | Web pages and images    | _`HTML_ROOT`_    | `public_html/`       |
    | Documentation           | _`DOC_ROOT`_     | `docs/`              |
    | Examples                | _`EXAMPLE_ROOT`_ | `examples/`          |
    | User directory          | _`USER_ROOT`_    | `bin/user/`          |


## Location of executables in a pip install

If you use a pip install, the location of the executables will depend on how the
pip installation was done.

| Install method                    | Commands                                                                     | Location of executables |
|-----------------------------------|------------------------------------------------------------------------------|-------------------------|
| Virtual environment (recommended) | `python3 -m venv ve`<br/>`. ve/bin/activate`<br/>`pip3 install weewx`        | `./ve/bin/`             |
| pip, no sudo, with `--user`       | `pip3 install weewx --user`                                                  | `~/.local/bin/`         |
| pip, no sudo, no `--user`         | `pip3 install weewx`                                                         | `~/.local/bin/`         |
| pip with sudo (not recommended)   | `sudo pip3 install weewx`                                                    | `/usr/local/bin/` (1)   |
| Virtual environment with `--user` | `python3 -m venv ve`<br/>`. ve/bin/activate`<br/>`pip3 install weewx --user` | Not allowed             |

(1) Checked on Ubuntu 22.02 and Rocky v9.1


## Log files

In the default configuration, WeeWX writes its status to the system log.
This is where to find the system log for each platform.

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
        The log file is likely to contain only severe log messages.

If the default for your system is inconvenient, or does not provide the logging
fidelity that you require, then you may want to consider logging to a separate,
rotating log file. See the wiki article 
[_Logging to rotating files_](https://github.com/weewx/weewx/wiki/WeeWX-v4-and-logging#logging-to-rotating-files).
