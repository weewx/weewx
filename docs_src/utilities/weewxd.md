# weewxd

The `weewxd` application is the heart of WeeWX.  It collects data from
hardware, processes the data, archives the data, then generates reports
from the data.

It can be run directly, or in the background as a daemon.  When it is run
directly, `weewxd` emits LOOP and ARCHIVE data to stdout.

Specify `--help` to see how it is used:
```
weewxd --help
```
```
Usage: weewxd --help
       weewxd --version
       weewxd config_file [--daemon] [--pidfile=PIDFILE] 
                          [--exit]   [--loop-on-init]
                          [--log-label=LABEL]
           
  Entry point to the weewx weather program. Can be run directly, or as a daemon
  by specifying the '--daemon' option.

Arguments:
    config_file: The weewx configuration file to be used.


Options:
  -h, --help            show this help message and exit
  -d, --daemon          Run as a daemon
  -p PIDFILE, --pidfile=PIDFILE
                        Store the process ID in PIDFILE
  -v, --version         Display version number then exit
  -x, --exit            Exit on I/O and database errors instead of restarting
  -r, --loop-on-init    Retry forever if device is not ready on startup
  -n LABEL, --log-label=LABEL
                        Label to use in syslog entries
```
