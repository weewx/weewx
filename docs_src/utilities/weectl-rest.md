# weectl rest

Use the `weectl` subcommand `rest` to list the configured RESTful upload
services, and to force an upload on demand.

RESTful services are the uploaders that publish your data to online weather
networks, such as the Weather Underground, CWOP, PWSWeather, WOW, AWEKAS, and
the WeeWX station registry. They are configured in the `[StdRESTful]` section of
`weewx.conf`.

Specify `--help` to see the actions and options.

## List RESTful services

    weectl rest list
        [--config=FILENAME]

The `list` action lists all the RESTful services configured in
`restful_services` (under `[Engine] / [[Services]]`), along with whether each
one is enabled. A service counts as _enabled_ if it has been configured with
everything it needs to run (for example, the Weather Underground requires a
`station` and `password`). For example:

```
$ weectl rest list
Using configuration file /home/ted_user/weewx-data/weewx.conf

Service              Enabled   Class
StationRegistry         N      weewx.restx.StdStationRegistry
Wunderground            Y      weewx.restx.StdWunderground
PWSweather              N      weewx.restx.StdPWSweather
CWOP                    N      weewx.restx.StdCWOP
WOW                     N      weewx.restx.StdWOW
AWEKAS                  N      weewx.restx.StdAWEKAS
```

## Force an upload on demand

    weectl rest run [NAME ...]
        [--config=FILENAME]

In normal operation, WeeWX uploads to a RESTful service only when a new archive
record arrives, and only as often as the service's posting schedule allows. The
action `weectl rest run` forces an immediate upload of the most recent archive
record in the database, irrespective of the normal posting schedule (the
`stale` and `post_interval` limits are ignored). It uses the same configuration
file that `weewxd` uses.

The names of the services to upload to can be given on the command line,
separated by spaces. Names are _case insensitive_, and can be given either as
the short name shown by `weectl rest list` (for example, `Wunderground`) or as
the class name (for example, `StdWunderground`). Use `weectl rest list` to
determine the names.

For example, to force an upload to the Weather Underground and CWOP:

    weectl rest run Wunderground CWOP

If no names are given, then all _enabled_ services will be run:

    # Upload to all enabled services:
    weectl rest run

Only enabled services are uploaded to. If you name a service that is not
enabled, it will be skipped with a notice.

## Options

### --config

Path to the configuration file. Default is `~/weewx-data/weewx.conf`.

### --help

Show the help message, then exit.
