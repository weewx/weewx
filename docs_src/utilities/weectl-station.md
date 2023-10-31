# weectl station

Use the `weectl` subcommand `station` to manage the data for a station,
including its configuration file.

Specify `--help` to see the actions and options. 

See the section [_Options_](#options) below for details of the various options.

## Create a new station data directory

    weectl station create
        [--driver=DRIVER]
        [--location=LOCATION]
        [--altitude=ALTITUDE,(foot|meter)]
        [--latitude=LATITUDE] [--longitude=LONGITUDE]
        [--register=(y,n) [--station-url=URL]]
        [--units=(us|metricwx|metric)]
        [--skin-root=DIRECTORY]
        [--sqlite-root=DIRECTORY]
        [--html-root=DIRECTORY]
        [--user-root=DIRECTORY]
        [--docs-root=DIRECTORY]
        [--examples-root=DIRECTORY]
        [--no-prompt]
        [--config=FILENAME]
        [--dist-config=FILENAME]
        [--dry-run]

The `create` action will create a directory and populate it with station data.
After the command completes, the directory will contain:

- a configuration file called `weewx.conf`;
- documentation;
- examples;
- utility files; and
- skins.

This action is typically used to create the initial station configuration when
installing WeeWX for the first time.  It can also be used to create
configurations for multiple stations.

If invoked without any options, the `create` action will prompt you for
various settings, such as the type of hardware you are using, the station
altitude and location, etc.

Use the option `--no-prompt` to create a configuration without prompts. This
will use settings specified as options, and default values for any setting
not specified. This is useful when creating a station with an automated script.
For example,

    weectl station create --no-prompt --driver=weewx.drivers.vantage \
        --altitude="400,foot" --latitude=45.1 --longitude=-105.9 \ 
        --location="My Special Station"

will create a station with the indicated values. Default values will be used
for any setting that is not specified.


## Reconfigure an existing station

    weectl station reconfigure
        [--driver=DRIVER]
        [--location=LOCATION]
        [--altitude=ALTITUDE,(foot|meter)]
        [--latitude=LATITUDE] [--longitude=LONGITUDE]
        [--register=(y,n) [--station-url=URL]]
        [--units=(us|metricwx|metric)]
        [--skin-root=DIRECTORY]
        [--sqlite-root=DIRECTORY]
        [--html-root=DIRECTORY]
        [--no-backup]
        [--no-prompt]
        [--config=FILENAME]
        [--dry-run]

The `reconfigure` action will modify the contents of an existing configuration
file. It is often used to change drivers.

If invoked without any options, `reconfigure` will prompt you for settings.

Use the option `--no-prompt` to reconfigure without prompts. This will use
the settings specified as options, and existing values for anything that is
not specified.

For example, to keep all settings, but change to the Vantage driver you would
use

    weectl station reconfigure --no-prompt --driver=weewx.drivers.vantage


## Upgrade an existing station

    weectl station upgrade
        [--docs-root=DIRECTORY]
        [--examples-root=DIRECTORY]
        [--skin-root=DIRECTORY]
        [--what (config|docs|examples|util|skins)]
        [--no-backup]
        [--no-prompt]
        [--config=FILENAME]
        [--dist-config=FILENAME]
        [--dry-run]

When you upgrade WeeWX, only the code is upgraded; upgrades to WeeWX
do not modify the station data, specifically configuration file, database,
or skins.

Use the `upgrade` action to upgrade one or more of these items.

```
weectl station upgrade
```

When invoked with no options, the `upgrade` action upgrades only the
documentation, examples, and utility files. By default, the configuration file
and skins are not upgraded. This is to avoid overwriting any changes you might
have made.

If you wish to upgrade the skins, you must specify `--what skins`. This will
put the current version of the skins into `WEEWX_ROOT`, leaving timestamped
copies of your old skins.

```
weectl station upgrade --what skins
```

If you wish to upgrade the configuration file, specify `--what config`.  This
is rarely necessary, since WeeWX is usually backward compatible.

```
weectl station upgrade --what config
```

## Options

In what follows, `WEEWX_ROOT` is the directory holding the configuration file.
For a pip install, this is typically `~/weewx-data`. For a Debian, Redhat, or
SUSE install, it is `/etc/weewx`.

### --driver=DRIVER

Which driver to use. Default is `weewx.drivers.simulator`.

### --location=LOCATION

A description of your station, such as `--location="A small town in Rongovia"`
Default is `WeeWX`.

### --altitude=ALTITUDE

The altitude of your station, along with the unit it is measured in. For
example, `--altitude=50,meter`. Note that the unit is measured in the singular
(`foot`, not `feet`). Default is `"0,foot"`.

### --latitude=LATITUDE

The station latitude in decimal degrees. Negative for the southern hemisphere.
Default is `0`.

### --longitude=LONGITUDE

The station longitude in decimal degrees. Negative for the western hemisphere.
Default is `0`.

### --register=(y|n)

Whether to include the station in the WeeWX registry and [map](https://weewx.com/stations.html).
If you choose to register your station, you must also specify a unique URL for
your station with option `--station-url`. Default is `n` (do not register).

### --station-url=URL

A unique URL for the station.  The station URL identifies each station in
the WeeWX registry and map.

Example: `--station-url=https://www.wunderground.com/dashboard/pws/KNDPETE15`.
No default.

### --units=UNIT_SYSTEM

What units to use for your reports. Options are `us`, `metricwx`, or `metric`.
See the Appendix [_Units_](../../custom/appendix/#units) for details. Default
is `us`.

### --config=FILENAME

Path to the configuration file, *relative to `WEEWX_ROOT`*.
If the filename starts with a slash (`/`), it is an absolute path.
Default is `weewx.conf`.

### --weewx-root=DIR

The `WEEWX_ROOT` directory. This is typically `~/weewx-data` or `/etc/weewx`.

### --skin-root=DIR

The location of the directory holding the skins *relative to `WEEWX_ROOT`*.
If the directory starts with a slash (`/`), it is an absolute path.
Default is `skins`.

### --sqlite-root=DIR

The location of the directory holding the SQLite database *relative to
`WEEWX_ROOT`*. If the directory starts with a slash (`/`), it is an absolute
path. Default is `skins`.

### --html-root=DIR

Where generated HTML files should be placed, *relative to `WEEWX_ROOT`*.
If the directory starts with a slash (`/`), it is an absolute path.
Default is `public_html`.

### --user-root=DIR

Where user extensions can be found, *relative to `WEEWX_ROOT`*.
If the directory starts with a slash (`/`), it is an absolute path.
Default is `bin/user`.

### --docs-root=DIR

Where the WeeWX documentation can be found, *relative to `WEEWX_ROOT`*.
If the directory starts with a slash (`/`), it is an absolute path.
Default is `docs`.

### --examples-root=DIR

Where the WeeWX examples can be found, *relative to `WEEWX_ROOT`*.
If the directory starts with a slash (`/`), it is an absolute path.
Default is `examples`.

### --what

By default, the `upgrade` action will upgrade the documentation, examples,
and utility files. However, you can specify exactly what gets upgraded by
using the `--what` option.

The `--what` option understands the following:

* config - the configuration file
* docs - the documentation
* examples - the example extensions
* util - the system utility files
* skins - the report templates

For example, to upgrade the configuration file and skins only, you would
specify

```
weectl station upgrade --what config skins
```

!!! Note
    The `--what` option does not take an equal sign (`=`). Just list the
    desired things to be upgraded, without commas between them.

### --no-backup

If `weectl station` changes your configuration file or skins, it will save a
timestamped copy of the original. If you specify `--no-backup`, then it will
not save a copy.

### --no-prompt

Generally, the utility will prompt for values unless `--no-prompt` has been
set. When `--no-prompt` is specified, the values to be used are the default
values, replaced with whatever options have been set on the command line.
For example,

```
weectl station create --driver='weewx.drivers.vantage' --no-prompt
```

will cause the defaults to be used for all values except `--driver`.

### --dry-run

With option `--dry-run` you can test what `weect station` would do
without actually doing it. It will print out the steps, but not
actually write anything.