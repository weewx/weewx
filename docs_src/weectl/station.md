# weectl station

## `weectl station`

The subcommand `weectl station` manages user data. Running `weectl station --help` will give you
more information about its four actions `create`, `reconfigure`, `upgrade`, and `upgrade-skins`:

```
% weectl station --help
usage: weectl station create [--config=CONFIG-PATH] \
                             [--dist-config=DIST-CONFIG-PATH]] \
                             [--driver=DRIVER] \
                             [--location=LOCATION] \
                             [--altitude=ALTITUDE,{foot|meter}] \
                             [--latitude=LATITUDE] [--longitude=LONGITUDE] \
                             [--register={y,n} [--station-url=STATION_URL]] \
                             [--units={us,metricwx,metric}] \
                             [--skin-root=SKIN_ROOT] \
                             [--sqlite-root=SQLITE_ROOT] \
                             [--html-root=HTML_ROOT] \
                             [--user-root=USER_ROOT] \
                             [--docs-root=DOCS_ROOT] \
                             [--examples-root=EXAMPLES_ROOT] \
                             [--no-prompt] \
                             [--dry-run]

       weectl station reconfigure [--config=CONFIG-PATH] \ 
                                  [--driver=DRIVER] \
                                  [--location=LOCATION] \
                                  [--altitude=ALTITUDE,{foot|meter}] \
                                  [--latitude=LATITUDE] [--longitude=LONGITUDE] \
                                  [--register={y,n} [--station-url=STATION_URL]] \
                                  [--units={us,metricwx,metric}] \
                                  [--skin-root=SKIN_ROOT] \
                                  [--sqlite-root=SQLITE_ROOT] \
                                  [--html-root=HTML_ROOT] \
                                  [--no-prompt] \
                                  [--no-backup] \
                                  [--dry-run]

       weectl station upgrade [--config=CONFIG-PATH] \
                              [--dist-config=DIST-CONFIG-PATH]] \
                              [--docs-root=DOCS_ROOT] \
                              [--examples-root=EXAMPLES_ROOT] \
                              [--skin-root=SKIN_ROOT] \
                              [--what [{config,docs,examples,util,skins} ... ] \
                              [--no-prompt] \
                              [--no-backup] \
                              [--dry-run]

Manages the user data area, including the configuration file and skins

optional arguments:
  -h, --help            show this help message and exit

Which action to take:
  {create,reconfigure,upgrade}
    create              Create a user data area, including a configuration
                        file.
    reconfigure         Reconfigure a station configuration file.
    upgrade             Upgrade any combination of the configuration file,
                        docs, examples, daemon utility files, and skins.
```

In the documentation that follows,  the exact output will depend on
your operating system and username. What is shown below is for Linux and user `tkeffer`.

## `weectl station create`

This action will create a new area for user data. When done, the area will include

- A configuration file, `weewx.conf`;
- Documentation;
- Examples;
- Daemon utility files; and
- Skins.

`weectl station create` is most useful when installing using pip, which only installs the
WeeWX software, not the user data to go along with it. To do the latter, you must use this action.

By contrast, package installers create the necessary user data as part of their one-step approach.
Nevertheless, you may want to create a second user data area, perhaps to support a second
instrument &mdash; in that case, this action may be useful.

Running `weectl station create --help` will show its options.

```
% weectl station create --help
usage: weectl station create [--config=CONFIG-PATH] \
                             [--driver=DRIVER] \
                             [--location=LOCATION] \
                             [--altitude=ALTITUDE,{foot|meter}] \
                             [--latitude=LATITUDE] [--longitude=LONGITUDE] \
                             [--register={y,n} [--station-url=STATION_URL]] \
                             [--units={us,metricwx,metric}] \
                             [--skin-root=SKIN_ROOT] \
                             [--sqlite-root=SQLITE_ROOT] \
                             [--html-root=HTML_ROOT] \
                             [--user-root=USER_ROOT] \
                             [--docs-root=DOCS_ROOT] \
                             [--examples-root=EXAMPLES_ROOT] \
                             [--no-prompt] \
                             [--dry-run]

Create a new user data area, including a configuration file. In what follows,
WEEWX_ROOT is the directory that contains the configuration file. For
example, if "--config=/home/tkeffer/weewx-data/weewx.conf", then WEEWX_ROOT
will be "/home/tkeffer/weewx-data".

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG-PATH  Path to configuration file. It must not already exist.
                        Default is "/home/tkeffer/weewx-data/weewx.conf".
  --driver DRIVER       Driver to use. Default is "weewx.drivers.simulator".
  --location LOCATION   A description of the station. This will be used for
                        report titles. Default is "WeeWX".
  --altitude ALTITUDE,{foot|meter}
                        The station altitude in either feet or meters. For
                        example, "750,foot" or "320,meter". Default is "0,
                        foot".
  --latitude LATITUDE   The station latitude in decimal degrees. Default is
                        "0.00".
  --longitude LONGITUDE
                        The station longitude in decimal degrees. Default is
                        "0.00".
  --register {y,n}      Register this station in the weewx registry? Default
                        is "n" (do not register).
  --station-url STATION_URL
                        Unique URL to be used if registering the station.
                        Required if the station is to be registered.
  --units {us,metricwx,metric}
                        Set display units to us, metricwx, or metric. Default
                        is "us".
  --skin-root SKIN_ROOT
                        Where to put the skins, relatve to WEEWX_ROOT. Default
                        is "skins".
  --sqlite-root SQLITE_ROOT
                        Where to put the SQLite database, relative to
                        WEEWX_ROOT. Default is "archive".
  --html-root HTML_ROOT
                        Where to put the generated HTML and images, relative
                        to WEEWX_ROOT. Default is "public_html".
  --user-root USER_ROOT
                        Where to put the "user" directory, relative to
                        WEEWX_ROOT. Default is "bin/user"
  --docs-root DOCS_ROOT
                        Where to put the documentation, relative to
                        WEEWX_ROOT. Default is "docs".
  --examples-root EXAMPLES_ROOT
                        Where to put the examples, relative to WEEWX_ROOT.
                        Default is "examples".
  --no-prompt           Do not prompt. Use default values.
  --dry-run             Print what would happen, but do not actually do it.
```

### Options

#### `--config`

Path to the configuration file to be created. The directory of the path will become the value for
`WEEWX_ROOT` in the configuration file. Default is `~/weewx-data/weewx.conf`.

#### `--driver`

Which driver to use. Default is `simulator`.

#### `--location`

A description of your station, such as `--location="A small town in Rongovia"`

#### `--altitude`

The altitude of your station, along with the unit it is measured in. For example, 
`--altitude=50,meter`. Note that the unit is measured in the singular (`foot`, not `feet`).

#### `--latitude`

The station latitude in decimal degrees. Negative for the southern hemisphere.

#### `--longitude`

The station longitude in decimal degrees. Negative for the western hemisphere.

#### `--register`

Whether to include the station in the WeeWX registry and [map](https://weewx.com/stations.html).
If you set `--register`, you must also specify a unique URL for your station with
option `--station-url`.

#### `--station-url`

A unique URL for your station. Example: `--station-url=https://www.wunderground.com/dashboard/pws/KNDPETE15`.

#### `--units`

What units to use for your reports. Choices are `us`, `metricwx`, or `metric`. See the Appendix 
[_Units_](../../custom/appendix/#units) for details.

#### `--no-prompt`

Generally, the utility will prompt for values unless `--no-prompt` has been set. With 
`--no-prompt`, the values to be used are the default values, replaced with whatever options have 
been set on the command line. For example,

```shell
weectl station create --driver='weewx.drivers.vantage' --no-prompt
```

will cause the defaults to be used for all values except `--driver`, which will use the Vantage
driver.

#### `--dry-run`

With option `--dry-run` you can test what `weect station create` will do without actually
touching storage. It will print out the steps, but not actually write anything.

#### root options

"Root options" include

`--skin-root`<br/>
`--sqlite-root`<br/>
`--html-root`<br/>
`--user-root`<br/>
`--docs-root`<br/>
`--examples-root`

All of these root options are *relative to `WEEWX_ROOT`*. Of course, like any other path, if the
option starts with a slash (`/`), it becomes an absolute path. So, for example,

```shell
--html-root=/var/www/html/
```

will cause HTML files to be put in the traditional system WWW directory `/var/www/html/`.



## `weectl station reconfigure`

This action will reconfigure your configuration file `weewx.conf`. Unless option `--no-prompt` has been specified, it will prompt you with your old settings, and give you a chance to change them. 

Running `weectl station reconfigure --help` will show you its options.

```
% weectl station reconfigure  --help
usage: weectl station reconfigure [--config=CONFIG-PATH] \ 
                                  [--driver=DRIVER] \
                                  [--location=LOCATION] \
                                  [--altitude=ALTITUDE,{foot|meter}] \
                                  [--latitude=LATITUDE] [--longitude=LONGITUDE] \
                                  [--register={y,n} [--station-url=STATION_URL]] \
                                  [--units={us,metricwx,metric}] \
                                  [--skin-root=SKIN_ROOT] \
                                  [--sqlite-root=SQLITE_ROOT] \
                                  [--html-root=HTML_ROOT] \
                                  [--no-prompt] \
                                  [--no-backup] \
                                  [--dry-run]

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG-PATH  Path to configuration file. Default is
                        "/home/tkeffer/weewx-data/weewx.conf"
  --driver DRIVER       Driver to use. Default is "weewx.drivers.simulator".
  --location LOCATION   A description of the station. This will be used for
                        report titles. Default is "WeeWX".
  --altitude ALTITUDE,{foot|meter}
                        The station altitude in either feet or meters. For
                        example, "750,foot" or "320,meter". Default is "0,
                        foot".
  --latitude LATITUDE   The station latitude in decimal degrees. Default is
                        "0.00".
  --longitude LONGITUDE
                        The station longitude in decimal degrees. Default is
                        "0.00".
  --register {y,n}      Register this station in the weewx registry? Default
                        is "n" (do not register).
  --station-url STATION_URL
                        Unique URL to be used if registering the station.
                        Required if the station is to be registered.
  --units {us,metricwx,metric}
                        Set display units to us, metricwx, or metric. Default
                        is "us".
  --skin-root SKIN_ROOT
                        Where to put the skins, relatve to WEEWX_ROOT. Default
                        is "skins".
  --sqlite-root SQLITE_ROOT
                        Where to put the SQLite database, relative to
                        WEEWX_ROOT. Default is "archive".
  --html-root HTML_ROOT
                        Where to put the generated HTML and images, relative
                        to WEEWX_ROOT. Default is "public_html".
  --no-prompt           Do not prompt. Use default values.
  --no-backup           Do not backup the old configuration file.
  --dry-run             Print what would happen, but do not actually do it.
```

When used with the `--no-prompt` option, `weectl station reconfigure` will modify specific parameters with no interaction. For example, this would set the station altitude to 35 feet:

```shell
weectl station reconfigure --altitude=35,foot --no-prompt
```

This would change the driver to a user-installed netatmo driver:

```shell
weectl station reconfigure --driver=user.netatmo --no-prompt
```

Other options are as under [`weectl station create`](#weectl-station-create) above.


## `weectl station upgrade`

This action can upgrade any combination of your configuration file, documentation, examples,
daemon utility files, and skins.

Running `weectl station upgrade --help` will show you its options.

```
% weectl station upgrade --help
usage: weectl station upgrade [--config=CONFIG-PATH] \
                              [--dist-config=DIST-CONFIG-PATH]] \
                              [--docs-root=DOCS_ROOT] \
                              [--examples-root=EXAMPLES_ROOT] \
                              [--skin-root=SKIN_ROOT] \
                              [--what [{config,docs,examples,util,skins} ... ] \
                              [--no-prompt] \
                              [--no-backup] \
                              [--dry-run]

Upgrade an existing user data area, including any combination of the
configuration file, docs, examples, daemon utility files, and skins. In what
follows, WEEWX_ROOT is the directory that contains the configuration
file. For example, if "--config=/home/tkeffer/weewx-data/weewx.conf", then
WEEWX_ROOT will be "/home/tkeffer/weewx-data".

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG-PATH  Path to configuration file. Default is
                        "/home/tkeffer/weewx-data/weewx.conf"
  --dist-config DIST-CONFIG-PATH
                        Use configuration file DIST-CONFIG-PATH as the new
                        configuration file. Default is to retrieve it from
                        package resources. The average user is unlikely to
                        need this option.
  --docs-root DOCS_ROOT
                        Where to put the new documentation, relative to
                        WEEWX_ROOT. Default is "docs".
  --examples-root EXAMPLES_ROOT
                        Where to put the new examples, relative to WEEWX_ROOT.
                        Default is "examples".
  --skin-root SKIN_ROOT
                        Where to put the skins, relative to WEEWX_ROOT.
                        Default is "skins".
  --what {config,docs,examples,util,skins} [{config,docs,examples,util,skins} ...]
                        What to upgrade. Default is to upgrade the
                        configuration file, documentation, examples, and
                        daemon utility files.
  --no-prompt           Do not prompt. Use default values.
  --no-backup           Do not backup the old configuration file.
  --dry-run             Print what would happen, but do not actually do it.
```

#### `--config`

Path to the configuration file to be updated. The directory of the path will become the value for
`WEEWX_ROOT` in the configuration file. Default is `~/weewx-data/weewx.conf`.

#### `--what`

By default, `weectl station upgrade` will upgrade the configuration file, documentation, examples,
and daemon utility files. However, you can customize exactly what gets upgraded. 

!!! Note
    The `--what` option does not take an equal sign (`=`). Just list the desired things to be
    upgraded, without commas between.

For example, to upgrade the configuration file and skins only, you would specify

```
weectl station upgrade --what config skins
```

#### root options

"Root options" include

`--skin-root`<br/>
`--docs-root`<br/>
`--examples-root`

All of these root options are *relative to `WEEWX_ROOT`*. Of course, like any other path, if the
option starts with a slash (`/`), it becomes an absolute path. So, for example,

```shell
--docs-root=/usr/local/doc/weewx
```

will cause documentation files to be put in `/usr/local/doc/weewx`.
