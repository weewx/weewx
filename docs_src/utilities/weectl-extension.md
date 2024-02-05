# weectl extension

Use the `weectl` subcommand `extension` to manage WeeWX extensions.

Specify `--help` to see the actions and options:
```
weectl extension --help
```

## List installed extensions

    weectl extension list [--config=FILENAME]

This action will list all the extensions that you have installed.


## Install an extension

     weectl extension install (FILE|DIR|URL)
        [--config=FILENAME]
        [--dry-run] [--yes] [--verbosity=N]

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
        [--config=FILENAME]
        [--dry-run] [--yes] [--verbosity=N] [-y]

This action uninstalls an extension. Use the [action
`list`](#list-installed-extensions) to see what to use for `NAME`.

For example, this would uninstall the extension called `windy`:
```shell
weectl extension uninstall windy
```


## Examples

These examples illustrate how to use the extension installer to install, list,
and uninstall the `windy` extension.

Do a dry run of installing an uploader for the Windy website, maximum
verbosity:

``` shell
% weectl extension install https://github.com/matthewwall/weewx-windy/archive/master.zip --dry-run --verbosity=3
weectl extension install https://github.com/matthewwall/weewx-windy/archive/master.zip --dry-run --verbosity=3
Using configuration file /Users/joe_user/weewx-data/weewx.conf
This is a dry run. Nothing will actually be done.
Install extension 'https://github.com/matthewwall/weewx-windy/archive/master.zip'? y
Extracting from zip archive /var/folders/xm/72q6zf8j71x8df2cqh0j9f6c0000gn/T/tmpjusc3qrv
  Request to install extension found in directory /var/folders/xm/72q6zf8j71x8df2cqh0j9f6c0000gn/T/tmpo0oq1u34/weewx-windy-master/.
  Found extension with name 'windy'.
  Copying new files...
    Fake copying from '/var/folders/xm/72q6zf8j71x8df2cqh0j9f6c0000gn/T/tmpo0oq1u34/weewx-windy-master/bin/user/windy.py' to '/Users/joe_user/weewx-data/bin/user/windy.py'
  Fake copied 1 files.
  Adding services to service lists.
    Added new service user.windy.Windy to restful_services.
  Adding sections to configuration file
    Merged extension settings into configuration file
Saving installer file to /Users/joe_user/weewx-data/bin/user/installer/windy.
Finished installing extension windy from https://github.com/matthewwall/weewx-windy/archive/master.zip.
This was a dry run. Nothing was actually done.
```

Do it for real, default verbosity:

```
% weectl extension install https://github.com/matthewwall/weewx-windy/archive/master.zip
Using configuration file /Users/joe_user/weewx-data/weewx.conf
Install extension 'https://github.com/matthewwall/weewx-windy/archive/master.zip'? y
Extracting from zip archive /var/folders/xm/72q6zf8j71x8df2cqh0j9f6c0000gn/T/tmpcc92m0oq
Saving installer file to /Users/joe_user/weewx-data/bin/user/installer/windy.
Saved configuration dictionary. Backup copy at /Users/joe_user/weewx-data/weewx.conf.20231222135954.
Finished installing extension windy from https://github.com/matthewwall/weewx-windy/archive/master.zip.
```

List the results:

```
% weectl extension list
Extension Name    Version   Description
windy             0.7       Upload weather data to Windy.
```

Uninstall the extension without asking for confirmation:

```
% weectl extension uninstall windy -y
Using configuration file /Users/joe_user/weewx-data/weewx.conf
Finished removing extension 'windy'
```


## Options

These are options used by most of the actions.

### --config

Path to the configuration file. Default is `~/weewx-data/weewx.conf`.

### --dry-run

Show what would happen if the action was run, but do not actually make any
writable changes.

### --help

Show the help message, then exit.

### --verbosity=(0|1|2|3)

How much information to display (0-3).

### -y | --yes

Do not ask for confirmation. Just do it.
