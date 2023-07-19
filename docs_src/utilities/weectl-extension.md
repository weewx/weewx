# weectl extension

Use the `weectl` subcommand `extension` to manage WeeWX extensions.

Specify `--help` to see the actions and options:
```
weectl extension --help
```
```
usage: weectl extension list
            [--config=FILENAME]

       weectl extension install (FILE|DIR|URL)
            [--config=FILENAME]
            [--dry-run] [--verbosity=N]

       weectl extension uninstall NAME
            [--config=FILENAME]
            [--dry-run] [--verbosity=N]

Manages WeeWX extensions

optional arguments:
  -h, --help            show this help message and exit

Which action to take:
  {list,install,uninstall}
    list                List all installed extensions
    install             Install an extension contained in FILE (such as
                        pmon.tar.gz), directory (DIR), or from an URL.
    uninstall           Uninstall an extension
```


## Common options

These are options used by most of the actions.

### --help

Show the help message, then exit.

### --config

Path to the configuration file. Default is `~/weewx-data/weewx.conf`.

### --dry-run

Show what would happen if the action was run, but do not actually make any
writable changes.

### --verbosity=(0|1|2|3)

How much information to display (0-3).


## List installed extensions

    weectl extension list
        [--config=FILENAME] [--dry-run]

This action will list all the extensions that you have installed.


## Install an extension

    weectl extension install (FILE|DIR|URL)

This action will install an extension from a zip file, tar file, directory, or
URL.

For example, this would install the `windy` extension from the latest zip file
located at `github.com`:
```shell
weectl extension install https://github.com/matthewwall/weewx-windy/archive/master.zip
```

This would install the `windy` extension from a compressed tar archive in the
current directory:
```shell
weectl extension install windy-0.1.tgz
```

This would install the `windy` extension from a zip file in the `Downloads`
directory:
```shell
weectl extension install ~/Downloads/windy-0.1.zip
```


## Uninstall an extension 

    weectl extension uninstall NAME

This action uninstalls an extension. Use the `list` action to see what to use
for `NAME`. 

For example, this would uninstall the extension called `windy`:
```shell
weectl extension uninstall windy
```


## Examples {#install-examples}

These examples illustrate how to use the extension installer to install, list,
and uninstall the `windy` extension.

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
