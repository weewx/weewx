# weectl station

## `weectl station`

`weectl station` manages user data. Running `weectl station --help` will give you more information about its four actions `create`, `reconfigure`, `upgrade`, and `upgrade-skins`:

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
                             [--no-prompt]

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
                                  [--no-prompt]

       weectl station upgrade [--config=CONFIG-PATH]
       weectl station upgrade-skins [--config=CONFIG-PATH]

Manages the configuration file and skins

optional arguments:
  -h, --help            show this help message and exit

Which action to take:
  {create,reconfigure,upgrade,upgrade-skins}
    create              Create a user data area, including a config file
    reconfigure         Reconfigure a station config file
    upgrade             Upgrade the configuration file, docs, and examples
    upgrade-skins       Upgrade the skins
```

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

Running `weectl station create --help` will show its options. The exact output will depend on
your operating system and username. What is shown below is for macOS and user `tkeffer`.

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
                             [--no-prompt]

In what follows, WEEWX_ROOT is the directory that contains the
configuration file. For example, if "--config=/Users/tkeffer/weewx-
data/weewx.conf", then WEEWX_ROOT will be "/Users/tkeffer/weewx-data".

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
                        $WEEWX_ROOT. Default is "lib/user"
  --docs-root DOCS_ROOT
                        Where to put the documentation, relative to
                        $WEEWX_ROOT. Default is "docs".
  --examples-root EXAMPLES_ROOT
                        Where to put the examples, relative to $WEEWX_ROOT.
                        Default is "examples".
  --no-prompt           If set, do not prompt. Use default values.
```

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
                                  [--no-prompt]

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
                        0.00.
  --longitude LONGITUDE
                        The station longitude in decimal degrees. Default is
                        0.00.
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
```