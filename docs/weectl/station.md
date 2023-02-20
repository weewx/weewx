# weectl station

## `weectl station`

The subcommand `weectl station` manages user data. Running `weectl station --help` will give you
more information about its four actions `create`, `reconfigure`, `upgrade`, and `upgrade-skins`:

```shell
% weectl station --help
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
                                  [--dry-run]

       weectl station upgrade [--config=CONFIG-PATH] \
                              [--docs-root=DOCS_ROOT] \
                              [--examples-root=EXAMPLES_ROOT]
                              [--dry-run]

       weectl station upgrade-skins [--config=CONFIG-PATH] \
                                    [--dry-run]

Manages the configuration file and skins

optional arguments:
  -h, --help            show this help message and exit

Which action to take:
  {create,reconfigure,upgrade,upgrade-skins}
    create              Create a user data area, including a configuration
                        file.
    reconfigure         Reconfigure a station configuration file.
    upgrade             Upgrade the configuration file, docs, examples, and
                        utility files.
    upgrade-skins       Upgrade the skins.
```

In the documentation that follows,  the exact output will depend on
your operating system and username. What is shown below is for macOS and user `tkeffer`.

## `weectl station create`

This action will create a new area for user data. When done, the area will include

- A configuration file, `weewx.conf`
- Skins
- Examples
- Documentation

`weectl station create` is most useful when installing using pip, which only installs the
WeeWX software, not the user data to go along with it. To do the latter, you must use this action.

By contrast, package installers create the necessary user data as part of their one-step approach.
Nevertheless, you may want to create a second user data area, perhaps to support a second
instrument &mdash; in that case, this action may be useful.

Running `weectl station create --help` will show its options.

```shell
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
example, if "--config=/Users/tkeffer/weewx-data/weewx.conf", then WEEWX_ROOT
will be "/Users/tkeffer/weewx-data".

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG-PATH  Path to configuration file. It must not already exist.
                        Default is "/Users/tkeffer/weewx-data/weewx.conf".
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
                        Where to put the skins, relatve to $WEEWX_ROOT.
                        Default is "skins".
  --sqlite-root SQLITE_ROOT
                        Where to put the SQLite database, relative to
                        $WEEWX_ROOT. Default is "archive".
  --html-root HTML_ROOT
                        Where to put the generated HTML and images, relative
                        to WEEWX_ROOT. Default is "public_html".
  --user-root USER_ROOT
                        Where to put the "user" directory, relative to
                        $WEEWX_ROOT. Default is "bin/user"
  --docs-root DOCS_ROOT
                        Where to put the documentation, relative to
                        $WEEWX_ROOT. Default is "docs".
  --examples-root EXAMPLES_ROOT
                        Where to put the examples, relative to $WEEWX_ROOT.
                        Default is "examples".
  --no-prompt           If set, do not prompt. Use default values.
  --dry-run             Print what would happen, but do not actually do it.
```

### Notable options

Most options are self-explanatory. A few are not.

#### `--no-prompt`

Generally, the utility will prompt for values unless `--no-prompt` has been set. If it has beeen
set, the values to be used are the default values, replaced with whatever options have been set.
For example,

```shell
weectl station create --driver='weewx.drivers.vantage' --no-prompt
```

will cause the defaults to be used for all values except `--driver`, which will use the Vantage
driver.

#### `--config`

Path to the configuration file to be created. The directory of the path will become the value for
`WEEWX_ROOT` in the configuration file. Default is `~/weewx-data/weewx.conf`.

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

``` shell
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
                                  [--dry-run]

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG-PATH  Path to configuration file. Default is
                        "/Users/tkeffer/weewx-data/weewx.conf"
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
                        Where to put the skins, relatve to $WEEWX_ROOT.
                        Default is "skins".
  --sqlite-root SQLITE_ROOT
                        Where to put the SQLite database, relative to
                        $WEEWX_ROOT. Default is "archive".
  --html-root HTML_ROOT
                        Where to put the generated HTML and images, relative
                        to WEEWX_ROOT. Default is "public_html".
  --no-prompt           If set, do not prompt. Use default values.
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

This action will upgrade your configuration file, documentation, examples, and
daemon configuration files. The skins will not be touched.

Running `weectl station upgrade --help` will show you its options.

``` shell
% weectl station upgrade --help
usage: weectl station upgrade [--config=CONFIG-PATH] \
                              [--docs-root=DOCS_ROOT] \
                              [--examples-root=EXAMPLES_ROOT]
                              [--dry-run]

Upgrade an existing user data area, including the configuration file, docs,
examples, and utility files. In what follows, WEEWX_ROOT is the
directory that contains the configuration file. For example, if "--
config=/Users/tkeffer/weewx-data/weewx.conf", then WEEWX_ROOT will be
"/Users/tkeffer/weewx-data".

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG-PATH  Path to configuration file. Default is
                        "/Users/tkeffer/weewx-data/weewx.conf"
  --docs-root DOCS_ROOT
                        Where to put the new documentation, relative to
                        $WEEWX_ROOT. Default is "docs".
  --examples-root EXAMPLES_ROOT
                        Where to put the new examples, relative to
                        $WEEWX_ROOT. Default is "examples".
  --dry-run             Print what would happen, but do not actually do it.
```

## `weectl station upgrade-skins`

This action will upgrade your skins. Your old skins will be saved as a timestamped backup.
Your configuration file will not be touched.

Running `weectl station upgrade-skins --help` will show you its options.

``` shell
% weectl station upgrade-skins --help
usage: weectl station upgrade-skins [--config=CONFIG-PATH] \
                                    [--skin-root=SKIN_ROOT] \
                                    [--no-prompt] \
                                    [--dry-run]

Upgrade skins to the latest version. A backup will be made first. In what
follows, WEEWX_ROOT is the directory that contains the configuration
file. For example, if "--config=/Users/tkeffer/weewx-data/weewx.conf", then
WEEWX_ROOT will be "/Users/tkeffer/weewx-data".

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG-PATH  Path to configuration file. Default is
                        "/Users/tkeffer/weewx-data/weewx.conf"
  --skin-root SKIN_ROOT
                        Where to put the skins, relatve to WEEWX_ROOT. Default
                        is "skins".
  --no-prompt           If set, do not prompt. Use default values.
  --dry-run             Print what would happen, but do not actually do it.

```

