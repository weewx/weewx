# weewxd

The `weewxd` application is the heart of WeeWX.  It collects data from
hardware, processes the data, archives the data, then generates reports
from the data.

It can be run directly, or in the background as a daemon.  When it is run
directly, `weewxd` emits LOOP and ARCHIVE data to stdout.  When it is run
as a daemon, it will fork, output will go to log, and the process ID will be
written to the `pidfile`.

Specify `--help` to see how it is used:
```
weewxd --help
```
```
usage: weewxd --help
       weewxd --version
       weewxd [FILENAME|--config=FILENAME]
              [--daemon]
              [--pidfile=PIDFILE]
              [--exit]
              [--loop-on-init]
              [--log-label=LABEL]

The main entry point for WeeWX. This program will gather data from your
station, archive its data, then generate reports.

positional arguments:
  FILENAME

optional arguments:
  -h, --help            show this help message and exit
  --config FILENAME     Use configuration file FILENAME
  -d, --daemon          Run as a daemon
  -p PIDFILE, --pidfile PIDFILE
                        Store the process ID in PIDFILE
  -v, --version         Display version number then exit
  -x, --exit            Exit on I/O and database errors instead of restarting
  -r, --loop-on-init    Retry forever if device is not ready on startup
  -n LABEL, --log-label LABEL
                        Label to use in syslog entries

Specify either the positional argument FILENAME, or the optional argument
using --config, but not both.
```
