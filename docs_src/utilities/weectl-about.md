# weectl

The command `weectl` is the entry point for most WeeWX utilities. To see the
various utilities available, run it with the `--help` option:

```
$ weectl --help

usage: weectl -v|--version
       weectl -h|--help
       weectl database --help
       weectl debug --help
       weectl extension --help
       weectl station --help

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit

Available subcommands:
  {database,debug,extension,station}
    database            Manages WeeWX databases.
    debug               Generate debug info.
    extension           List, install, or uninstall extensions.
    station             Create, modify, or upgrade a station data area.
```

## [weectl database](../weectl-database)
Use this subcommand to manage your WeeWX database

## [weectl debug](../weectl-debug)
Use this subcommand to generate output that captures your WeeWX environment
and configuration file. This is useful for remote debugging.

## [weectl extension](../weectl-extension)
Use this subcommand to install, uninstall, and list WeeWX extensions.

## [weectl station](../weectl-station)
Use this subcommand to create and manage stations.