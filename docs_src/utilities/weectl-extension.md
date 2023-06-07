# weectl extension

Use the `weectl` subcommand `extension` to manage WeeWX extensions.

Specify `--help` to see the actions and options:
```
weectl extension --help
```
```
usage: weectl extension list [--config=CONFIG-PATH]

       weectl extension install {FILE|DIR|URL}
           [--config=CONFIG-PATH]
           [--dry-run] [--verbosity=N]

       weectl extension uninstall NAME
           [--config=CONFIG-PATH]
           [--dry-run] [--verbosity=N]

Manages WeeWX extensions

optional arguments:
  -h, --help            show this help message and exit

Which action to take:
  {list,install,uninstall}
    list                List all installed extensions
    install             Install an extension contained in FILENAME (such as
                        pmon.tar.gz), or from a DIRECTORY, or from an URL.
    uninstall           Uninstall an extension
```


## `weectl extension list`

This action will list all installed extensions.

Specify `--help` to see the options:
```
weectl extension list --help
```
```
usage: weectl extension list [--config=CONFIG-PATH]

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG-PATH  Path to configuration file. Default is
                        "/Users/tkeffer/weewx-data/weewx.conf".
  --verbosity N         How much information to display {0-3}.
```

### `--config=FILENAME`

The utility is pretty good about guessing where the WeeWX configuration file
is located. If it guesses wrong, use this option to specify the configuration
file.


## `weectl extension install`

This action will install an extension from a zipfile, tarball, directory, or
URL.

Specify `--help` to see the options:
```
weectl extension install --help
```
```
usage:   weectl extension install {FILE|DIR|URL}
           [--config=CONFIG-PATH]
           [--dry-run] [--verbosity=N]

positional arguments:
  source                Location of the extension. It can be a path to a
                        zipfile or tarball, a path to an unpacked directory,
                        or an URL pointing to a zipfile or tarball.

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG-PATH  Path to configuration file. Default is
                        "/Users/tkeffer/weewx-data/weewx.conf".
  --dry-run             Print what would happen, but do not actually do it.
  --verbosity N         How much information to display {0-3}.
```

### `--config=FILENAME`

The utility is pretty good about guessing where the WeeWX configuration file
is located. If it guesses wrong, use this option to specify the configuration
file.

### `--dry-run`

This option will show you what the installer would do, but will not actually
do it.

### `--verbosity=N`

This option selects how much information to show as the installation proceeds.


## `weectl extension uninstall`

This action uninstalls an extension.

Specify `--help` to see the options:
```
weectl extension uninstall --help
```
```
usage:   weectl extension uninstall NAME
           [--config=CONFIG-PATH]
           [--dry-run] [--verbosity=N]

positional arguments:
  name                  Name of the extension to uninstall.

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG-PATH  Path to configuration file. Default is
                        "/Users/tkeffer/weewx-data/weewx.conf".
  --dry-run             Print what would happen, but do not actually do it.
  --verbosity N         How much information to display {0-3}.
```

### `--config=FILENAME`

The utility is pretty good about guessing where the WeeWX configuration file
is located. If it guesses wrong, use this option to specify the configuration
file.

### `--dry-run`

This option will show you what the installer would do, but will not actually
do it.

### `--verbosity=N`

This option selects how much information to show as the installation proceeds.


## Examples

These examples illustrate how to use the extension installer.

Do a dry run of installing an uploader for the Windy website, maximum
verbosity:

``` shell
% weectl extension install https://github.com/matthewwall/weewx-windy/archive/master.zip --dry-run --verbosity=3
Request to install 'https://github.com/matthewwall/weewx-windy/archive/master.zip'
This is a dry run. Nothing will actually be done.
Extracting from zip archive /var/folders/xm/72q6zf8j71x8df2cqh0j9f6c0000gn/T/tmpuvuc_c0k
  Request to install extension found in directory /var/folders/xm/72q6zf8j71x8df2cqh0j9f6c0000gn/T/tmpif_nj_0g/weewx-windy-master/
  Found extension with name 'windy'
  Copying new files
    Copying from '/var/folders/xm/72q6zf8j71x8df2cqh0j9f6c0000gn/T/tmpif_nj_0g/weewx-windy-master/bin/user/windy.py' to '/Users/Shared/weewx/bin/user/windy.py'
  Copied 0 files
  Adding services to service lists
    Added new service user.windy.Windy to restful_services
  Adding sections to configuration file
    Merged extension settings into configuration file
Saving installer file to /Users/Shared/weewx/bin/user/installer/windy
Finished installing extension windy from https://github.com/matthewwall/weewx-windy/archive/master.zip
This was a dry run. Nothing was actually done.
```

Do it for real, default verbosity:

```
% weectl extension install https://github.com/matthewwall/weewx-windy/archive/master.zip
Request to install 'https://github.com/matthewwall/weewx-windy/archive/master.zip'
Extracting from zip archive /var/folders/xm/72q6zf8j71x8df2cqh0j9f6c0000gn/T/tmpk8ggl4qr
Saving installer file to /Users/Shared/weewx/bin/user/installer/windy
Saved configuration dictionary. Backup copy at /Users/Shared/weewx/weewx.conf.20230110152037
Finished installing extension windy from https://github.com/matthewwall/weewx-windy/archive/master.zip
```

List the results:

```
% weectl extension list                                                                 
Extension Name    Version   Description
windy             0.7       Upload weather data to Windy.
```

Uninstall the extension:

```
% weectl extension uninstall windy
Request to remove extension 'windy'
Finished removing extension 'windy'
```
