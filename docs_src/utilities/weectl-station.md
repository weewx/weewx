# weectl station

Use the `weectl` subcommand `station` to manage the user data for a
station, including its configuration file.

Specify `--help` to see the actions and options.

In the documentation that follows,  the exact output will depend on your
operating system and username. What is shown below is for Linux and user
`tkeffer`.

## Create a new user data area

    weectl station create
        [--driver=DRIVER]
        [--location=LOCATION]
        [--altitude=ALTITUDE,(foot|meter)]
        [--latitude=LATITUDE] [--longitude=LONGITUDE]
        [--register=(y,n) [--station-url=STATION_URL]]
        [--units=(us|metricwx|metric)]
        [--skin-root=SKIN_ROOT]
        [--sqlite-root=SQLITE_ROOT]
        [--html-root=HTML_ROOT]
        [--user-root=USER_ROOT]
        [--docs-root=DOCS_ROOT]
        [--examples-root=EXAMPLES_ROOT]
        [--no-prompt]
        [--config=CONFIG-PATH]
        [--dist-config=DIST-CONFIG-PATH]
        [--dry-run]

This action will create a new area for user data. After the command completes,
the area will include

- A configuration file, `weewx.conf`;
- Documentation;
- Examples;
- Utility files; and
- Skins.

`weectl station create` is typically used when installing using pip, or when
you want to create multiple stations.

### Create user data with prompting

If invoked without any options, `weectl station create` will prompt you for various settings,
such as the type of hardware you are using, the station altitude and location, etc. This is what
most users will want.

### Create user data without prompting

A new user data area can be created without prompting by using option `--no-prompt`. This
is most useful when creating a station with an automated script. For
example,

    weectl station create --no-prompt --driver=weewx.drivers.vantage \
        --altitude="400,foot" --latitude=45.1 --longitude=-105.9 \ 
        --location="My Special Station"

will create a station with the indicated values. If a value is not specified, a default will
be used.

See the section [_Common options_](#common-options) for details of the various options.

## Reconfigure an existing station

    weectl station reconfigure
        [--driver=DRIVER]
        [--location=LOCATION]
        [--altitude=ALTITUDE,(foot|meter)]
        [--latitude=LATITUDE] [--longitude=LONGITUDE]
        [--register=(y,n) [--station-url=STATION_URL]]
        [--units=(us|metricwx|metric)]
        [--skin-root=SKIN_ROOT]
        [--sqlite-root=SQLITE_ROOT]
        [--html-root=HTML_ROOT]
        [--no-backup]
        [--no-prompt]
        [--config=CONFIG-PATH] 
        [--dry-run]

This action will reconfigure the contents of an existing configuration file (generally named
`weewx.conf`). 

It is often used for changing drivers.

### Reconfigure with prompting

If invoked without the `--no-prompt` option, `weectl station reconfigure` will prompt you for new
settings.

### Reconfigure without prompting

If the option `--no-prompt` is specified, `weectl station reconfigure` will reconfigure the
configuration file using whatever options you've specified on the command line.

For example, to keep all settings, but change to the Vantage driver you would use

    weectl station reconfigure --no-prompt --driver=weewx.drivers.vantage


## Upgrade an existing station

    weectl station upgrade
        [--docs-root=DOCS_ROOT]
        [--examples-root=EXAMPLES_ROOT]
        [--skin-root=SKIN_ROOT]
        [--what (config|docs|examples|util|skins)...]
        [--no-backup]
        [--no-prompt]
        [--config=CONFIG-PATH]
        [--dist-config=DIST-CONFIG-PATH]]
        [--dry-run]


If you installed using pip, then do an upgrade using pip, it will only upgrade the code base. It
does not touch the user data area. Use this action to upgrade all or part of the user data area.

It can also be useful for upgrading a package install. While these generally 


### --what

By default, `weectl station upgrade` will upgrade the configuration file, documentation, examples,
and utility files. However, you can customize exactly what gets upgraded.

!!! Note
    The `--what` option does not take an equal sign (`=`). Just list the
    desired things to be upgraded, without commas between them.

For example, to upgrade the configuration file and skins only, you would
specify

```
weectl station upgrade --what config skins
```

## Common options {#common-options}

In what follows, `WEEWX_ROOT` is the directory holding the configuration file. For a pip
install, this is typically `~/weewx-data/`. For package installs, it is usually `/etc/weewx/`.

### --driver=DRIVER

Which driver to use. Default is `weewx.drivers.simulator`.

### --location=LOCATION

A description of your station, such as `--location="A small town in Rongovia"` Default
is `WeeWX`.

### --altitude=ALTITUDE

The altitude of your station, along with the unit it is measured in. For
example, `--altitude=50,meter`. Note that the unit is measured in the singular
(`foot`, not `feet`). Default is `"0,foot"`.

### --latitude=LATITUDE

The station latitude in decimal degrees. Negative for the southern hemisphere. Default is
`0`.

### --longitude=LONGITUDE

The station longitude in decimal degrees. Negative for the western hemisphere. Default is `0`.

### --register={y|n}

Whether to include the station in the WeeWX registry and [map](https://weewx.com/stations.html). If
you choose to register your station, you must also specify a unique URL for your station with
option `--station-url`. Default is `n` (do not register).

### --station-url=URL

A unique URL for your station.

Example: `--station-url=https://www.wunderground.com/dashboard/pws/KNDPETE15`. No default.

### --units=UNIT_SYSTEM

What units to use for your reports. Options are `us`, `metricwx`, or `metric`.
See the Appendix [_Units_](../../custom/appendix/#units) for details. Default is `us`.

### --skin-root=SKIN_ROOT

The location of the directory holding the skins *relative to `WEEWX_ROOT`*. Of course, like any
other path, if the option starts with a slash (`/`), it becomes an absolute path. Default is
`skins`.

### --sqlite-root=SQLITE_ROOT

The location of the directory holding the SQLite database *relative to `WEEWX_ROOT`*. Of course,
like any other path, if the option starts with a slash (`/`), it becomes an absolute path. Default
is `skins`.

### --html-root=HTML_ROOT

Where generated HTML files should be placed, *relative to `WEEWX_ROOT`*.  Of course, like any other
path, if the option starts with a slash (`/`), it becomes an absolute path. Default is
`public_html`.

### --user-root=USER_ROOT

Where user extensions can be found, *relative to `WEEWX_ROOT`*. Of course, like any other path, if
the option starts with a slash (`/`), it becomes an absolute path. Default is `bin/user`.

### --docs-root=DOCS_ROOT

Where the WeeWX documentation can be found, *relative to `WEEWX_ROOT`*. Of course, like any other
path, if the option starts with a slash (`/`), it becomes an absolute path. Default is `docs`.

### --examples-root=EXAMPLES_ROOT

Where the WeeWX examples can be found, *relative to `WEEWX_ROOT`*. Of course, like any other path,
if the option starts with a slash (`/`), it becomes an absolute path. Default is `examples`.

### --no-backup

Generally, if `weectl station` changes your configuration file, it will save a timestamped version
of your original configuration file. If you specify `--no-backup`, then it will not save a copy.

### --no-prompt

Generally, the utility will prompt for values unless `--no-prompt` has been
set. With `--no-prompt`, the values to be used are the default values,
replaced with whatever options have been set on the command line. For example,

```
weectl station create --driver='weewx.drivers.vantage' --no-prompt
```

will cause the defaults to be used for all values except `--driver`, which will
use the Vantage driver.

### --config=FILENAME

Path to the configuration file to be created. The directory of the path will
become the value for `WEEWX_ROOT` in the configuration file. Default is
`~/weewx-data/weewx.conf`.

### --dry-run

With option `--dry-run` you can test what `weect station` would do
without actually doing it. It will print out the steps, but not
actually write anything.
