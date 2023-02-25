# Where to find things

Here is a summary of the layout for the different install methods, along with the symbolic names used for each role. These names are used throughout the documentation.

!!! Note
    The install locations below are *relative to _`WEEWX_ROOT`_*. See Python's documentation on
    [`os.path.join()`](https://docs.python.org/3.7/library/os.path.html#os.path.join) for the 
    results of a joining two absolute paths (summary: the 2nd path wins).


=== "Debian"

    | Role                    | Symbolic name     | Nominal value                  |
    |-------------------------|-------------------|--------------------------------|
    | WeeWX root directory    | _`WEEWX_ROOT`_   | `/`                             |
    | Executables             | _`BIN_ROOT`_     | `/usr/share/weewx/`             |
    | Configuration directory | _`CONFIG_ROOT`_  | `/etc/weewx/`                   |
    | Skins and templates     | _`SKIN_ROOT`_    | `/etc/weewx/skins/`             |
    | SQLite databases        | _`SQLITE_ROOT`_  | `/var/lib/weewx/`               |
    | Web pages and images    | _`HTML_ROOT`_    | `/var/www/html/weewx/`          |
    | Documentation           | _`DOC_ROOT`_     | `/usr/share/doc/weewx/`         |
    | Examples                | _`EXAMPLE_ROOT`_ | `/usr/share/doc/weewx/examples/`|
    | User directory          | _`USER_ROOT`_    | `/usr/share/weewx/user`         |
    | Log file                |                  | `/var/log/syslog`               |

=== "RedHat/openSUSE"

    | Role                    | Symbolic name    | Nominal value                          |
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
    | Log file                |                  | `/var/log/messages`                    |

=== "Pip (including macOS)"

    | Role                    | Symbolic name    | Nominal value        |
    |-------------------------|------------------|----------------------|
    | WeeWX root directory    | _`WEEWX_ROOT`_   | `~/weewx-data`       |
    | Executables             | _`BIN_ROOT`_     | `~/.local/bin`       |
    | Configuration directory | _`CONFIG_ROOT`_  | `./`                 |
    | Skins and templates     | _`SKIN_ROOT`_    | `./skins/`           |
    | SQLite databases        | _`SQLITE_ROOT`_  | `./archive/`         |
    | Web pages and images    | _`HTML_ROOT`_    | `./public_html/`     |
    | Documentation           | _`DOC_ROOT`_     | `./docs`             |
    | Examples                | _`EXAMPLE_ROOT`_ | `./examples/`        |
    | User directory          | _`USER_ROOT`_    | `./bin/user`         |
    | Log file                |                  | `/var/log/syslog`    |
