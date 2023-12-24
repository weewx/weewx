# weectl

The command `weectl` is the entry point for most WeeWX utilities. To see the
various utilities available, run it with the `--help` option:

```
$ weectl --help
usage: weectl -v|--version
       weectl -h|--help
       weectl database --help
       weectl debug --help
       weectl device --help
       weectl extension --help
       weectl import --help
       weectl report --help
       weectl station --help

weectl is the master utility used by WeeWX. It can invoke several different
subcommands listed below. You can explore their utility by using the --help
option. For example, to find out what the 'database' subcommand can do, use
'weectl database --help'.

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit

Available subcommands:
  {database,debug,device,extension,import,report,station}
    database            Manage WeeWX databases.
    debug               Generate debug info.
    device              Manage your hardware.
    extension           List, install, or uninstall extensions.
    import              Import observation data.
    report              List and run WeeWX reports.
    station             Create, modify, or upgrade a station data area.
```
